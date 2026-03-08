"""merge_shared_questions.py - 공통 지문 문제 그룹 병합

'第X到Y题是根据下面一段话' 패턴을 감지하여
공통 지문을 공유하는 문제들을 하나의 question으로 병합합니다.

병합 후 question_num은 그룹의 첫 번째 번호를 사용합니다.
(예: Q31~Q33 → question_num=31, sub_questions=[31,32,33])
"""

import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from config import TRANSCRIPTION_CACHE

# 중국어 숫자 → 정수
_CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
       '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
       '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
       '二十': 20, '三十': 30, '四十': 40, '四十五': 45}


def cn_to_int(s):
    if s in _CN:
        return _CN[s]
    # 조합: 三十一 → 31
    if '十' in s:
        parts = s.split('十')
        tens = _CN.get(parts[0], 0) if parts[0] else 1
        ones = _CN.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    return 0


def detect_shared_groups(questions):
    """공통 지문 그룹 감지.
    반환: {start_qnum: [qnum1, qnum2, ...]} 매핑
    """
    groups = {}
    pattern = re.compile(r'第(.+?)到(.+?)题')

    for q in questions:
        for s in q.get("sentences", []):
            m = pattern.search(s["text"])
            if m and "根据" in s["text"]:
                start = cn_to_int(m.group(1))
                end = cn_to_int(m.group(2))
                if start > 0 and end > 0 and end > start:
                    groups[start] = list(range(start, end + 1))

    return groups


def merge_questions(questions, groups):
    """공통 지문 그룹을 병합."""
    # 병합 대상 번호 → 그룹 시작 번호 매핑
    member_to_leader = {}
    for leader, members in groups.items():
        for m in members:
            member_to_leader[m] = leader

    merged = []
    processed = set()

    for q in questions:
        qnum = q["question_num"]
        if qnum in processed:
            continue

        if qnum in groups:
            # 이 문제가 그룹 리더: 멤버들 병합
            member_nums = groups[qnum]
            all_sentences = []
            sub_questions = []

            for mnum in member_nums:
                mq = next((x for x in questions if x["question_num"] == mnum), None)
                if mq:
                    all_sentences.extend(mq.get("sentences", []))
                    sub_questions.append(mnum)
                    processed.add(mnum)

            merged.append({
                "question_num": qnum,
                "sub_questions": sub_questions,
                "sentences": all_sentences,
            })
        elif qnum in member_to_leader:
            # 이미 리더에서 처리됨, 스킵
            continue
        else:
            # 독립 문제
            merged.append(q)
            processed.add(qnum)

    return merged


def process_track(track_name, dry_run=False):
    """단일 트랙의 questions 병합 처리."""
    trans_path = TRANSCRIPTION_CACHE / f"{track_name}.json"
    if not trans_path.exists():
        return False

    with open(trans_path, encoding="utf-8") as f:
        data = json.load(f)

    questions = data.get("questions", [])
    if not questions:
        return False

    groups = detect_shared_groups(questions)
    if not groups:
        return False

    print(f"\n{track_name}: {len(groups)}개 공통 지문 그룹 감지")
    for leader, members in sorted(groups.items()):
        print(f"  Q{leader}~Q{members[-1]} ({len(members)}문제 → 1세트)")

    if dry_run:
        return True

    # 병합
    original_count = len(questions)
    merged = merge_questions(questions, groups)
    data["questions"] = merged

    # 저장
    with open(trans_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  {original_count}개 → {len(merged)}개 questions으로 병합 완료")
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    target_tracks = args if args else None

    # 대상 트랙 목록
    tracks_to_check = []
    for i in range(1, 136):
        t = f"TRACK{i:03d}"
        if target_tracks and t not in target_tracks:
            continue
        tracks_to_check.append(t)
    if dry_run:
        print("=== DRY RUN (변경 없음) ===")

    changed = 0
    for t in tracks_to_check:
        if process_track(t, dry_run=dry_run):
            changed += 1

    print(f"\n총 {changed}개 트랙 처리{'(미리보기)' if dry_run else ' 완료'}")


if __name__ == "__main__":
    main()
