"""fix_cache_pos.py - 기존 캐시의 품사/역할을 일괄 정규화

사용법:
  python fix_cache_pos.py --dry-run    # 교정 미리보기 (파일 변경 없음)
  python fix_cache_pos.py              # 실제 교정 실행
"""

import argparse
import io
import json
import shutil
import sys

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

from config import ANALYSIS_CACHE
from validator import normalize_part_of_speech, validate_role


def fix_cache(dry_run: bool = False):
    files = sorted(ANALYSIS_CACHE.glob("*.json"))
    print(f"대상 파일: {len(files)}개")

    total_pos_fixes = 0
    total_role_fixes = 0
    pos_stats: dict[str, dict[str, int]] = {}  # before → after → count

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        analyses = data.get("analyses", [])
        file_fixes = 0

        for s in analyses:
            # 품사 정규화
            for w in s.get("words", []):
                old_pos = w.get("part_of_speech", "")
                new_pos, changed = normalize_part_of_speech(old_pos)
                if changed:
                    if old_pos not in pos_stats:
                        pos_stats[old_pos] = {}
                    pos_stats[old_pos][new_pos] = pos_stats[old_pos].get(new_pos, 0) + 1
                    w["part_of_speech"] = new_pos
                    total_pos_fixes += 1
                    file_fixes += 1

            # 역할 정규화
            old_role = s.get("role", "")
            new_role, changed = validate_role(old_role)
            if changed:
                s["role"] = new_role
                total_role_fixes += 1
                file_fixes += 1

        if file_fixes > 0:
            track = path.stem
            print(f"  {track}: {file_fixes}건 교정")

            if not dry_run:
                # 백업
                bak_path = path.with_suffix(".json.bak")
                if not bak_path.exists():
                    shutil.copy2(path, bak_path)

                # 저장
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

    # 통계 출력
    print("\n=== 교정 통계 ===")
    print(f"품사 교정: {total_pos_fixes}건")
    print(f"역할 교정: {total_role_fixes}건")
    print(f"합계: {total_pos_fixes + total_role_fixes}건")

    if pos_stats:
        print("\n=== 품사 매핑 상세 ===")
        for old, mapping in sorted(pos_stats.items(), key=lambda x: -sum(x[1].values())):
            for new, count in mapping.items():
                print(f"  '{old}' → '{new}': {count}건")

    if dry_run:
        print("\n[DRY RUN] 파일 변경 없음. 실제 교정은 --dry-run 없이 실행하세요.")
    else:
        print("\n[완료] .bak 백업 생성 후 교정 적용됨.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="캐시 품사/역할 일괄 정규화")
    parser.add_argument("--dry-run", action="store_true", help="미리보기 (파일 변경 없음)")
    args = parser.parse_args()
    fix_cache(dry_run=args.dry_run)
