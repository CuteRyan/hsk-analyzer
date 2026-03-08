"""precision_trim.py - 2차 정밀 트리밍

이미 분할된 음원 파일에 FunASR을 다시 돌려서
원본 텍스트와 매칭되지 않는 앞/뒤 부분을 정밀하게 트리밍합니다.

사용법:
  python precision_trim.py TRACK135
  python precision_trim.py  # WARN이 있는 모든 트랙
"""

import io
import json
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from pydub import AudioSegment
from config import OUTPUT_DIR, TRANSCRIPTION_CACHE

SPLIT_AUDIO_DIR = OUTPUT_DIR / "audio_splits"


def strip_punc(text):
    return re.sub(r'[，。！？、；：""''（）《》【】\s,.!?;:\s]', '', text)


def get_question_text(track_name, q_num):
    """transcription JSON에서 해당 문제의 원본 텍스트 추출"""
    trans_path = TRANSCRIPTION_CACHE / f"{track_name}.json"
    if not trans_path.exists():
        return ""
    with open(trans_path, encoding="utf-8") as f:
        data = json.load(f)
    for q in data.get("questions", []):
        if q["question_num"] == q_num:
            return "".join(s["text"] for s in q.get("sentences", []))
    return ""


def find_trim_points(original_text, recognized_text, timestamps):
    """원본과 인식 텍스트를 비교하여 트리밍할 시점(ms)을 찾는다.

    반환: (trim_start_ms, trim_end_ms)
      - trim_start_ms: 앞에서 잘라야 할 시점 (이전 문제 잔여분 제거)
      - trim_end_ms: 뒤에서 잘라야 할 시점 (다음 문제 시작분 제거)
    """
    orig_clean = strip_punc(original_text)
    recog_clean = strip_punc(recognized_text)

    if not orig_clean or not recog_clean or not timestamps:
        return 0, None

    # 구두점 제거된 인식 텍스트의 문자별 타임스탬프 매핑
    punc_pattern = re.compile(r'[，。！？、；：""''（）《》【】\s,.!?;:\s]')
    recog_raw = []
    raw_to_ts = []
    ts_idx = 0
    for ch in recognized_text:
        if punc_pattern.match(ch):
            continue
        recog_raw.append(ch)
        if ts_idx < len(timestamps):
            raw_to_ts.append(ts_idx)
        ts_idx += 1
    recog_raw_str = ''.join(recog_raw)

    # 원본 텍스트의 시작 부분을 인식 텍스트에서 찾기
    # (앞에 붙은 잔여분 감지)
    trim_start_ms = 0
    orig_start_key = orig_clean[:min(10, len(orig_clean))]
    start_pos = recog_raw_str.find(orig_start_key)

    if start_pos > 0:
        # 원본 시작 전에 잔여 텍스트가 있음 → 그 부분 트리밍
        if start_pos < len(raw_to_ts) and raw_to_ts[start_pos] < len(timestamps):
            # 원본 시작 지점에서 약간 앞(300ms)부터
            trim_start_ms = max(0, timestamps[raw_to_ts[start_pos]][0] - 300)
            print(f"    앞 트리밍: {start_pos}자 제거 "
                  f"(\"{recog_raw_str[:start_pos]}\" → {trim_start_ms/1000:.1f}s)")
    elif start_pos < 0:
        # 못 찾으면 더 짧은 키로 재시도
        for klen in [7, 5, 3]:
            key = orig_clean[:min(klen, len(orig_clean))]
            start_pos = recog_raw_str.find(key)
            if start_pos > 0:
                if start_pos < len(raw_to_ts) and raw_to_ts[start_pos] < len(timestamps):
                    trim_start_ms = max(0, timestamps[raw_to_ts[start_pos]][0] - 300)
                    print(f"    앞 트리밍: {start_pos}자 제거 (짧은키 매칭, {trim_start_ms/1000:.1f}s)")
                break

    # 원본 텍스트의 끝 부분을 인식 텍스트에서 찾기
    # (뒤에 붙은 다음 문제 시작분 감지)
    trim_end_ms = None
    orig_end_key = orig_clean[-min(10, len(orig_clean)):]
    end_pos = recog_raw_str.rfind(orig_end_key)

    if end_pos >= 0:
        end_char_pos = end_pos + len(orig_end_key)
        extra_chars = len(recog_raw_str) - end_char_pos
        if extra_chars > 2:
            # 원본 끝 이후에 추가 텍스트가 있음 → 그 부분 트리밍
            if end_char_pos < len(raw_to_ts) and raw_to_ts[end_char_pos] < len(timestamps):
                # 원본 끝나는 지점에서 약간 뒤(500ms)까지
                ts_idx_at_end = raw_to_ts[min(end_char_pos, len(raw_to_ts) - 1)]
                trim_end_ms = min(
                    timestamps[ts_idx_at_end][1] + 500,
                    timestamps[-1][1]
                )
                extra_text = recog_raw_str[end_char_pos:]
                print(f"    뒤 트리밍: {extra_chars}자 제거 "
                      f"(\"{extra_text[:20]}\" → {trim_end_ms/1000:.1f}s)")
    else:
        # 못 찾으면 더 짧은 키로 재시도
        for klen in [7, 5, 3]:
            key = orig_clean[-min(klen, len(orig_clean)):]
            end_pos = recog_raw_str.rfind(key)
            if end_pos >= 0:
                end_char_pos = end_pos + len(key)
                extra_chars = len(recog_raw_str) - end_char_pos
                if extra_chars > 2:
                    if end_char_pos < len(raw_to_ts) and raw_to_ts[end_char_pos] < len(timestamps):
                        ts_idx_at_end = raw_to_ts[min(end_char_pos, len(raw_to_ts) - 1)]
                        trim_end_ms = min(
                            timestamps[ts_idx_at_end][1] + 500,
                            timestamps[-1][1]
                        )
                        print(f"    뒤 트리밍: {extra_chars}자 제거 (짧은키, {trim_end_ms/1000:.1f}s)")
                break

    return trim_start_ms, trim_end_ms


def trim_file(mp3_path, track_name, q_num, model):
    """단일 분할 파일을 정밀 트리밍."""
    original = get_question_text(track_name, q_num)
    if not original:
        return False, "원본 텍스트 없음"

    # FunASR로 분할 파일 인식 (타임스탬프 포함)
    res = model.generate(input=str(mp3_path), batch_size_s=300)
    r = res[0]
    recognized = r.get("text", "")
    timestamps = r.get("timestamp", [])

    if not timestamps:
        return False, "타임스탬프 없음"

    # 현재 유사도 체크
    orig_clean = strip_punc(original)
    recog_clean = strip_punc(recognized)
    similarity = SequenceMatcher(None, orig_clean, recog_clean).ratio()

    if similarity >= 0.85:
        print(f"  {mp3_path.name}: 이미 OK ({similarity:.1%}), 스킵")
        return True, "already_ok"

    print(f"  {mp3_path.name}: {similarity:.1%} → 트리밍 시작")
    print(f"    원본({len(orig_clean)}자): {original[:50]}...")
    print(f"    인식({len(recog_clean)}자): {recognized[:50]}...")

    # 트리밍 포인트 찾기
    trim_start_ms, trim_end_ms = find_trim_points(original, recognized, timestamps)

    if trim_start_ms == 0 and trim_end_ms is None:
        print(f"    트리밍 포인트를 찾지 못함")
        return False, "no_trim_points"

    # 오디오 트리밍
    audio = AudioSegment.from_mp3(str(mp3_path))
    total_ms = len(audio)

    new_start = int(trim_start_ms) if trim_start_ms > 0 else 0
    new_end = int(trim_end_ms) if trim_end_ms is not None else total_ms

    if new_start >= new_end:
        print(f"    트리밍 범위 오류: {new_start}ms ~ {new_end}ms")
        return False, "invalid_range"

    trimmed = audio[new_start:new_end]

    # 원본 파일 덮어쓰기
    trimmed.export(str(mp3_path), format="mp3", bitrate="128k")

    old_dur = total_ms / 1000
    new_dur = len(trimmed) / 1000
    print(f"    트리밍 완료: {old_dur:.1f}s → {new_dur:.1f}s "
          f"(앞 {new_start/1000:.1f}s, 뒤 {(total_ms-new_end)/1000:.1f}s 제거)")

    return True, "trimmed"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target_tracks = args if args else None

    # 대상 파일 찾기
    split_files = sorted(SPLIT_AUDIO_DIR.glob("TRACK*-[0-9][0-9].mp3"))

    if target_tracks:
        split_files = [f for f in split_files
                       if any(f.stem.startswith(t) for t in target_tracks)]

    print(f"정밀 트리밍 대상: {len(split_files)}개 파일\n")

    # FunASR 모델 로드
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

    results = {"trimmed": 0, "already_ok": 0, "failed": 0}

    for mp3_path in split_files:
        stem = mp3_path.stem
        match = re.match(r'(TRACK\d+)-(\d+)$', stem)
        if not match:
            continue

        track_name = match.group(1)
        q_num = int(match.group(2))

        success, status = trim_file(mp3_path, track_name, q_num, model)
        if status == "trimmed":
            results["trimmed"] += 1
        elif status == "already_ok":
            results["already_ok"] += 1
        else:
            results["failed"] += 1

    print(f"\n{'='*60}")
    print(f"정밀 트리밍 완료:")
    print(f"  트리밍 적용: {results['trimmed']}개")
    print(f"  이미 OK: {results['already_ok']}개")
    print(f"  실패: {results['failed']}개")


if __name__ == "__main__":
    main()
