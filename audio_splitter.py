"""audio_splitter.py - FunASR 타임스탬프 기반 문제별 트랙 분할"""

import io
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional

from pydub import AudioSegment

from config import MP3_SOURCES, OUTPUT_DIR, TRANSCRIPTION_CACHE

# 분할된 오디오 저장 디렉토리
SPLIT_AUDIO_DIR = OUTPUT_DIR / "audio_splits"

# 한자 숫자 → 정수 변환
CN_NUM_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
    "二十一": 21, "二十二": 22, "二十三": 23, "二十四": 24, "二十五": 25,
}


def _cn_to_int(cn: str) -> int:
    if cn in CN_NUM_MAP:
        return CN_NUM_MAP[cn]
    return 0


def _strip_punc(text: str):
    """구두점 제거 → (raw_chars, raw_to_orig) 반환"""
    punc_pattern = re.compile(r'[，。！？、；：""''（）《》【】\s]')
    raw_chars = []
    raw_to_orig = []
    for i, ch in enumerate(text):
        if not punc_pattern.match(ch):
            raw_chars.append(ch)
            raw_to_orig.append(i)
    return raw_chars, raw_to_orig


def find_question_markers_with_timestamps(
    text: str, timestamps: list
) -> List[Tuple[int, int, int]]:
    """FunASR 타임스탬프를 이용하여 문제 마커 위치(번호, 시작ms, 원본텍스트위치)를 찾음.

    text: 구두점 포함 텍스트
    timestamps: 구두점 제외 원시 문자별 [start_ms, end_ms] 리스트

    반환: [(question_number, start_ms, orig_text_index), ...] 순서대로 정렬
    """
    raw_chars, raw_to_orig = _strip_punc(text)

    # ct-punc이 문자를 추가/변경하여 미스매치 가능 — 허용 범위 내면 진행
    ts_len = len(timestamps)
    raw_len = len(raw_chars)
    if abs(raw_len - ts_len) > max(10, raw_len * 0.05):
        return []
    # 짧은 쪽에 맞춤
    effective_len = min(raw_len, ts_len)

    # 한자 숫자 마커 후보 찾기
    single_markers = "一二三四五六七八九十"
    candidates = []

    for i, ch in enumerate(raw_chars):
        if i >= effective_len:
            break
        if ch not in single_markers:
            continue

        ts_ms = timestamps[i][0]

        # 복합 숫자 체크 (十一, 二十 등)
        combined = ch
        if ch == "十" and i + 1 < len(raw_chars) and raw_chars[i + 1] in "一二三四五六七八九":
            combined = ch + raw_chars[i + 1]
        elif ch in "二三" and i + 1 < len(raw_chars) and raw_chars[i + 1] == "十":
            if i + 2 < len(raw_chars) and raw_chars[i + 2] in "一二三四五六七八九":
                combined = ch + "十" + raw_chars[i + 2]
            else:
                combined = ch + "十"

        num = _cn_to_int(combined)
        if num == 0:
            num = _cn_to_int(ch)
        if num == 0:
            continue

        # 문맥 기반 필터링: 진짜 마커인지 확인
        # 마커 뒤에 오는 문자가 숫자 관련이 아니어야 함 (三天, 一下, 一趟 등 제외)
        if i + 1 < len(raw_chars):
            next_ch = raw_chars[i + 1]
            # "一下", "一趟", "一口", "三天", "三遍", "一千", "十分" 등 필터
            non_marker_followers = "下趟口天遍千百万亿分钟年月日号次个块元双杯件套把条只些样种台间层户所扇颗棵首篇部位名辆架座栋幢份本段落节课步周秒点半共起直"
            if next_ch in non_marker_followers:
                continue

        # 마커 앞 문맥 확인
        is_marker = False
        if i == 0:
            is_marker = True
        elif i > 0:
            orig_idx = raw_to_orig[i]
            before = text[:orig_idx].rstrip()
            if before and before[-1] in "。？！?!，,":
                is_marker = True
            elif before.endswith("第"):
                is_marker = True
            # 시간 갭 기반: 이전 문자와 3초 이상 갭이 있으면 마커로 판정
            elif i > 0 and timestamps[i][0] - timestamps[i - 1][1] > 3000:
                is_marker = True

        if not is_marker:
            continue

        candidates.append((num, ts_ms, i, raw_to_orig[i]))

    # 순차 필터링: 1부터 시작하여 순서대로 증가하는 마커만 유지
    if not candidates:
        return []

    candidates.sort(key=lambda x: (x[0], x[1]))

    result = []
    seen_nums = set()
    for num, ts_ms, raw_idx, orig_idx in candidates:
        if num not in seen_nums:
            if num == 1 or (num - 1) in seen_nums:
                result.append((num, ts_ms, orig_idx))
                seen_nums.add(num)

    result.sort(key=lambda x: x[0])
    return result


def split_track_text(track_name: str, text: str,
                     markers: List[Tuple[int, int, int]]) -> List[dict]:
    """텍스트를 문제별로 분할.

    markers: [(question_num, start_ms, orig_text_index), ...]

    반환: [{"question_num": int, "text": str, "start_ms": int}, ...]
    """
    if not markers:
        return [{"question_num": 1, "text": text, "start_ms": 0}]

    results = []
    for idx, (q_num, start_ms, orig_pos) in enumerate(markers):
        if idx + 1 < len(markers):
            end_pos = markers[idx + 1][2]
        else:
            end_pos = len(text)
        q_text = text[orig_pos:end_pos].strip()
        results.append({
            "question_num": q_num,
            "text": q_text,
            "start_ms": start_ms,
        })

    return results


def split_track_audio(mp3_path: Path, markers: List[Tuple[int, int, int]],
                      track_name: str, padding_ms: int = 500) -> List[Path]:
    """MP3를 문제별로 분할하여 저장.

    markers: [(question_num, start_ms, orig_text_index), ...]
    padding_ms: 마커 시작 전 여유 시간 (ms)

    반환: 생성된 파일 경로 리스트
    """
    if len(markers) <= 1:
        return []

    SPLIT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio = AudioSegment.from_mp3(str(mp3_path))
    total_ms = len(audio)

    output_files = []
    for idx, (q_num, start_ms, _) in enumerate(markers):
        seg_start = max(0, start_ms - padding_ms)

        if idx + 1 < len(markers):
            next_start = markers[idx + 1][1]
            seg_end = max(seg_start, next_start - padding_ms)
        else:
            seg_end = total_ms

        segment = audio[seg_start:seg_end]

        out_name = f"{track_name}-Q{q_num:02d}.mp3"
        out_path = SPLIT_AUDIO_DIR / out_name
        segment.export(str(out_path), format="mp3", bitrate="128k")
        output_files.append(out_path)

        dur = len(segment) / 1000
        print(f"    {out_name}: {dur:.1f}s "
              f"({seg_start/1000:.1f}s ~ {seg_end/1000:.1f}s)")

    return output_files


def get_timestamps_for_track(mp3_path: Path, model=None) -> Tuple[str, list]:
    """FunASR로 타임스탬프 포함 음성인식 실행.

    반환: (text, timestamps)
    """
    if model is None:
        from funasr import AutoModel
        model = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            device="cpu",
            disable_update=True,
        )

    res = model.generate(input=str(mp3_path), batch_size_s=300)
    r = res[0]
    return r.get("text", ""), r.get("timestamp", [])


def split_all_long_tracks(source: str = "listening",
                          min_chars: int = 200) -> dict:
    """긴 트랙(여러 문제)을 전부 분할.

    반환: {track_name: {"questions": [...], "audio_files": [...]}}
    """
    from funasr import AutoModel
    model = AutoModel(
        model="paraformer-zh",
        vad_model="fsmn-vad",
        punc_model="ct-punc",
        device="cpu",
        disable_update=True,
    )

    source_dir = MP3_SOURCES.get(source)
    trans_dir = TRANSCRIPTION_CACHE
    results = {}

    for f in sorted(trans_dir.glob("TRACK*.json")):
        track_name = f.stem
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        text = data.get("text", "")

        if len(text) < min_chars:
            continue

        mp3_path = source_dir / f"{track_name}.mp3"
        if not mp3_path.exists():
            continue

        print(f"\n{track_name} ({len(text)}자) 분석 중...")

        # 타임스탬프 재추출
        text_ts, timestamps = get_timestamps_for_track(mp3_path, model)

        # 문제 마커 찾기
        markers = find_question_markers_with_timestamps(text_ts, timestamps)
        if len(markers) <= 1:
            print(f"  단일 문제 트랙 (분할 불필요)")
            continue

        print(f"  {len(markers)}개 문제 감지: {[m[0] for m in markers]}")

        # 텍스트 분할
        questions = split_track_text(track_name, text_ts, markers)

        # 오디오 분할
        audio_files = split_track_audio(mp3_path, markers, track_name)

        results[track_name] = {
            "questions": questions,
            "audio_files": audio_files,
        }

    return results


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8",
            errors="replace", line_buffering=True
        )

    print("=== FunASR 타임스탬프 기반 문제 분할 ===\n")
    results = split_all_long_tracks()
    print(f"\n=== 완료: {len(results)}개 트랙 분할 ===")
    for name, data in results.items():
        print(f"  {name}: {len(data['questions'])}개 문제, "
              f"{len(data['audio_files'])}개 오디오 파일")
