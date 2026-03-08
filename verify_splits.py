"""verify_splits.py - 분할 음원 검증 스크립트

잘린 음원을 FunASR로 다시 텍스트 변환하여
원래 transcription JSON의 questions 텍스트와 대조합니다.

사용법:
  python verify_splits.py                    # 전체 검증
  python verify_splits.py TRACK010 TRACK041  # 특정 트랙만
"""

import io
import json
import re
import sys
import os
from pathlib import Path
from difflib import SequenceMatcher

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from config import OUTPUT_DIR, TRANSCRIPTION_CACHE

SPLIT_AUDIO_DIR = OUTPUT_DIR / "audio_splits"


def strip_punc(text):
    """구두점/공백 제거"""
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
            sentences = q.get("sentences", [])
            return "".join(s["text"] for s in sentences)
    return ""


def verify_track(track_name, model):
    """단일 트랙의 분할 음원 검증"""
    split_files = sorted(SPLIT_AUDIO_DIR.glob(f"{track_name}-[0-9][0-9].mp3"))
    if not split_files:
        return []

    results = []
    for mp3_path in split_files:
        stem = mp3_path.stem
        match = re.match(r'(TRACK\d+)-(\d+)$', stem)
        if not match:
            continue

        q_num = int(match.group(2))
        original = get_question_text(track_name, q_num)
        if not original:
            results.append({"file": stem, "status": "SKIP", "detail": "no original text"})
            continue

        try:
            res = model.generate(input=str(mp3_path), batch_size_s=300)
            recognized = res[0].get("text", "")
        except Exception as e:
            results.append({"file": stem, "status": "ERROR", "detail": str(e)})
            continue

        orig_clean = strip_punc(original)
        recog_clean = strip_punc(recognized)
        similarity = SequenceMatcher(None, orig_clean, recog_clean).ratio()

        if similarity >= 0.85:
            status = "OK"
        elif similarity >= 0.60:
            status = "WARN"
        else:
            status = "FAIL"

        results.append({
            "file": stem,
            "track": track_name,
            "q_num": q_num,
            "status": status,
            "similarity": round(similarity, 4),
            "orig_len": len(orig_clean),
            "recog_len": len(recog_clean),
            "original_preview": original[:80],
            "recognized_preview": recognized[:80],
        })

    return results


def main():
    # 대상 트랙 결정
    target_tracks = sys.argv[1:] if len(sys.argv) > 1 else None

    if not target_tracks:
        # 분할 음원이 있는 모든 트랙
        all_splits = sorted(SPLIT_AUDIO_DIR.glob("TRACK*-[0-9][0-9].mp3"))
        target_tracks = sorted(set(
            re.match(r'(TRACK\d+)', f.stem).group(1)
            for f in all_splits if re.match(r'(TRACK\d+)', f.stem)
        ))

    total_files = sum(
        len(list(SPLIT_AUDIO_DIR.glob(f"{t}-[0-9][0-9].mp3")))
        for t in target_tracks
    )
    print(f"검증 대상: {len(target_tracks)}개 트랙, {total_files}개 파일\n")

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

    all_results = []
    done = 0
    for track_name in target_tracks:
        print(f"--- {track_name} ---")
        track_results = verify_track(track_name, model)

        for r in track_results:
            done += 1
            if r["status"] == "SKIP":
                print(f"  [{done}/{total_files}] {r['file']}: SKIP")
            elif r["status"] == "ERROR":
                print(f"  [{done}/{total_files}] {r['file']}: ERROR - {r['detail']}")
            else:
                mark = {"OK": "O", "WARN": "!", "FAIL": "X"}[r["status"]]
                print(f"  [{done}/{total_files}] {r['file']}: [{mark}] {r['similarity']:.1%} "
                      f"({r['orig_len']}자 vs {r['recog_len']}자)")
                if r["status"] != "OK":
                    print(f"    원본: {r['original_preview']}")
                    print(f"    인식: {r['recognized_preview']}")

        all_results.extend(track_results)

    # 결과 저장
    output_path = OUTPUT_DIR / "split_verify_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # 요약
    print(f"\n{'='*60}")
    ok = sum(1 for r in all_results if r["status"] == "OK")
    warn = sum(1 for r in all_results if r["status"] == "WARN")
    fail = sum(1 for r in all_results if r["status"] == "FAIL")
    err = sum(1 for r in all_results if r["status"] == "ERROR")
    skip = sum(1 for r in all_results if r["status"] == "SKIP")
    print(f"검증 완료: {len(all_results)}개")
    print(f"  OK: {ok}  WARN: {warn}  FAIL: {fail}  ERROR: {err}  SKIP: {skip}")

    if warn + fail > 0:
        print(f"\n문제 파일:")
        for r in all_results:
            if r["status"] in ("WARN", "FAIL"):
                print(f"  {r['file']}: {r['similarity']:.1%} ({r['orig_len']}자 vs {r['recog_len']}자)")

    print(f"\n결과 저장: {output_path}")


if __name__ == "__main__":
    main()
