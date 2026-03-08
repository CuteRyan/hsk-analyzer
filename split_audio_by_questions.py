"""split_audio_by_questions.py - questions 배열 기반 오디오 분할

transcription JSON의 questions 배열 + FunASR 타임스탬프를 활용하여
복수 문제 트랙의 오디오를 문제별로 분할합니다.

정밀 분할: 각 문제의 첫 문장 시작 ~ 마지막 문장 끝 타임스탬프 사용.
"""

import io
import json
import re
import sys
import os
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from pydub import AudioSegment
from config import MP3_SOURCES, OUTPUT_DIR, TRANSCRIPTION_CACHE

SPLIT_AUDIO_DIR = OUTPUT_DIR / "audio_splits"


def strip_punc(text):
    """구두점/공백 제거하여 raw 문자열 반환"""
    return re.sub(r'[，。！？、；：""''（）《》【】\s,.!?;:\s]', '', text)


def build_raw_mapping(funasr_text):
    """FunASR 텍스트의 구두점 제거 + 타임스탬프 인덱스 매핑"""
    raw_chars = []
    raw_to_ts_idx = []
    ts_idx = 0
    punc_pattern = re.compile(r'[，。！？、；：""''（）《》【】\s,.!?;:\s]')

    for ch in funasr_text:
        if punc_pattern.match(ch):
            continue
        raw_chars.append(ch)
        raw_to_ts_idx.append(ts_idx)
        ts_idx += 1

    return ''.join(raw_chars), raw_to_ts_idx


def find_text_in_raw(search_text, raw_str, search_from=0):
    """search_text를 raw_str에서 찾아 (start_pos, end_pos) 반환.
    end_pos는 매칭된 텍스트의 마지막 문자 위치 (exclusive).

    여러 검색 전략 시도: 전체 → 마커제거 → 점점 짧게
    반환: (start_pos, end_pos) 또는 (None, None)
    """
    raw_search = strip_punc(search_text)
    if not raw_search:
        return None, None

    # 마커 제거 버전
    no_marker = strip_punc(
        re.sub(r'^[一二三四五六七八九十]+[、，,.\s]+', '', search_text))

    # 검색 후보: (검색키, 매칭 길이)
    candidates = []

    # 1) 전체 텍스트
    candidates.append(raw_search)
    # 2) 마커 제거
    if no_marker != raw_search:
        candidates.append(no_marker)

    for candidate in candidates:
        # 점점 짧은 키로 시도
        for slen in [len(candidate), 15, 8, 5, 3]:
            slen = min(slen, len(candidate))
            if slen <= 0:
                continue
            key = candidate[:slen]
            pos = raw_str.find(key, search_from)
            if pos >= 0:
                # 전체 candidate를 매칭하여 end 위치 결정
                full_pos = raw_str.find(candidate, search_from)
                if full_pos >= 0:
                    return full_pos, full_pos + len(candidate)
                else:
                    # 부분 매칭: 시작 위치는 찾았으나 전체는 못 찾음
                    return pos, pos + slen

    return None, None


def get_timestamp_at(pos, raw_to_ts_idx, timestamps, use_end=False):
    """raw 위치에 대응하는 타임스탬프(ms) 반환.
    use_end=True면 해당 문자의 end_ms 반환.
    """
    if pos is None or pos < 0:
        return None
    # pos가 범위를 넘으면 마지막으로 클램프
    pos = min(pos, len(raw_to_ts_idx) - 1)
    if pos < 0:
        return None
    ts_idx = raw_to_ts_idx[pos]
    if ts_idx >= len(timestamps):
        ts_idx = len(timestamps) - 1
    return timestamps[ts_idx][1 if use_end else 0]


def find_question_boundaries(q_sentences, raw_str, raw_to_ts_idx,
                              timestamps, search_from=0):
    """문제의 모든 문장에 대해 시작/끝 타임스탬프를 찾는다.

    반환: (start_ms, end_ms, new_search_from) 또는 (None, None, search_from)
    """
    if not q_sentences:
        return None, None, search_from

    # 첫 문장의 시작 위치 찾기
    first_text = q_sentences[0]["text"]
    first_start, _ = find_text_in_raw(first_text, raw_str, search_from)

    if first_start is None:
        # 전체 텍스트 연결해서 시도
        all_text = "".join(s["text"] for s in q_sentences)
        first_start, all_end = find_text_in_raw(all_text, raw_str, search_from)
        if first_start is not None:
            start_ms = get_timestamp_at(first_start, raw_to_ts_idx, timestamps)
            end_ms = get_timestamp_at(
                min(all_end - 1, len(raw_to_ts_idx) - 1),
                raw_to_ts_idx, timestamps, use_end=True)
            return start_ms, end_ms, (all_end if all_end else search_from)
        return None, None, search_from

    start_ms = get_timestamp_at(first_start, raw_to_ts_idx, timestamps)

    # 마지막 문장의 끝 위치 찾기
    last_text = q_sentences[-1]["text"]
    # 마지막 문장은 첫 문장 이후부터 검색
    last_search_from = first_start + 1
    _, last_end = find_text_in_raw(last_text, raw_str, last_search_from)

    if last_end is None:
        # 마지막 문장을 못 찾으면 첫 문장 기준으로 전체 텍스트 길이 추정
        all_raw = strip_punc("".join(s["text"] for s in q_sentences))
        last_end = first_start + len(all_raw)

    end_ms = get_timestamp_at(
        min(last_end - 1, len(raw_to_ts_idx) - 1),
        raw_to_ts_idx, timestamps, use_end=True)

    new_search = last_end if last_end else first_start + 1
    return start_ms, end_ms, new_search


def split_track(track_name, mp3_path, model, padding_before=500,
                padding_after=800):
    """단일 트랙을 questions 배열 기반으로 정밀 분할.

    padding_before: 시작점 앞 여유 (ms) - 문제 번호 마커 포함
    padding_after: 끝점 뒤 여유 (ms) - 여운/질문 후 무음 포함

    반환: 생성된 파일 경로 리스트
    """
    trans_path = TRANSCRIPTION_CACHE / f"{track_name}.json"
    with open(trans_path, encoding="utf-8") as f:
        trans_data = json.load(f)

    questions = trans_data.get("questions", [])
    if len(questions) < 2:
        return []

    # FunASR 타임스탬프 추출
    print(f"  FunASR 타임스탬프 추출 중...")
    res = model.generate(input=str(mp3_path), batch_size_s=300)
    r = res[0]
    funasr_text = r.get("text", "")
    timestamps = r.get("timestamp", [])

    if not timestamps:
        print(f"  경고: 타임스탬프 없음, 건너뜀")
        return []

    raw_str, raw_to_ts_idx = build_raw_mapping(funasr_text)

    # 각 문제의 시작/끝 타임스탬프 찾기
    question_bounds = []  # (q_num, start_ms, end_ms)
    search_from = 0

    for q in questions:
        q_num = q["question_num"]
        q_sentences = q.get("sentences", [])
        if not q_sentences:
            continue

        start_ms, end_ms, new_search = find_question_boundaries(
            q_sentences, raw_str, raw_to_ts_idx, timestamps, search_from)

        if start_ms is not None and end_ms is not None:
            question_bounds.append((q_num, start_ms, end_ms))
            search_from = new_search
            first_text = q_sentences[0]["text"]
            last_text = q_sentences[-1]["text"]
            print(f"    문제 {q_num}: {start_ms/1000:.1f}s ~ {end_ms/1000:.1f}s "
                  f"({(end_ms-start_ms)/1000:.1f}s) "
                  f"\"{first_text[:15]}...{last_text[-10:]}\"")
        else:
            first_text = q_sentences[0]["text"] if q_sentences else ""
            print(f"    문제 {q_num}: 위치 찾기 실패 - \"{first_text[:20]}...\"")

    if len(question_bounds) < 2:
        print(f"  경고: 시작 지점을 충분히 찾지 못함 "
              f"({len(question_bounds)}/{len(questions)})")
        return []

    # 오디오 로드 및 분할
    audio = AudioSegment.from_mp3(str(mp3_path))
    total_ms = len(audio)

    SPLIT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_files = []

    for idx, (q_num, start_ms, end_ms) in enumerate(question_bounds):
        # 시작: 본문 시작 전 여유 (문제 번호 마커 포함)
        seg_start = max(0, start_ms - padding_before)

        # 끝: 본문 끝 + 여유, 단 다음 문제 시작을 넘지 않도록
        seg_end = min(total_ms, end_ms + padding_after)
        if idx + 1 < len(question_bounds):
            next_start = question_bounds[idx + 1][1]
            # 다음 문제 시작 - 200ms 앞까지만 (겹침 방지)
            max_end = next_start - 200
            seg_end = min(seg_end, max(seg_start, max_end))

        segment = audio[seg_start:seg_end]

        out_name = f"{track_name}-{q_num:02d}.mp3"
        out_path = SPLIT_AUDIO_DIR / out_name
        segment.export(str(out_path), format="mp3", bitrate="128k")
        output_files.append(out_path)

        dur = len(segment) / 1000
        print(f"    -> {out_name}: {dur:.1f}s ({seg_start/1000:.1f}s ~ {seg_end/1000:.1f}s)")

    return output_files


def main():
    from config import MP3_SOURCES
    source_dir = MP3_SOURCES["listening"]

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target_tracks = args if args else None

    multi_tracks = []
    for i in range(1, 136):
        t = f"TRACK{i:03d}"
        if target_tracks and t not in target_tracks:
            continue
        trans_path = TRANSCRIPTION_CACHE / f"{t}.json"
        if not trans_path.exists():
            continue
        with open(trans_path, encoding="utf-8") as f:
            data = json.load(f)
        if len(data.get("questions", [])) >= 2:
            mp3 = source_dir / f"{t}.mp3"
            if mp3.exists():
                multi_tracks.append((t, mp3))

    print(f"=== 오디오 분할 시작: {len(multi_tracks)}개 트랙 ===\n")

    print("FunASR 모델 로딩 중...")
    from funasr import AutoModel
    model = AutoModel(
        model="paraformer-zh",
        vad_model="fsmn-vad",
        punc_model="ct-punc",
        device="cpu",
        disable_update=True,
    )
    print("모델 로딩 완료\n")

    results = {}
    for track_name, mp3_path in multi_tracks:
        print(f"\n{track_name} 처리 중...")
        try:
            files = split_track(track_name, mp3_path, model)
            results[track_name] = len(files)
            print(f"  완료: {len(files)}개 파일 생성")
        except Exception as e:
            print(f"  오류: {e}")
            import traceback
            traceback.print_exc()
            results[track_name] = 0

    print(f"\n=== 완료 ===")
    total = sum(results.values())
    print(f"총 {total}개 오디오 파일 생성")
    for t, n in results.items():
        status = f"{n}개" if n > 0 else "실패"
        print(f"  {t}: {status}")


if __name__ == "__main__":
    main()
