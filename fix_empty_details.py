"""fix_empty_details.py - meaning_detail 빈값을 GPT로 보충

사용법:
  python fix_empty_details.py --dry-run    # 대상 목록만 출력
  python fix_empty_details.py              # 실제 GPT 호출 + 캐시 업데이트
"""

import argparse
import io
import json
import sys
import time

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

from dotenv import load_dotenv

load_dotenv(override=True)

from openai import OpenAI  # noqa: E402

from config import ANALYSIS_CACHE, GPT_MODEL  # noqa: E402


def collect_empty_details() -> list[dict]:
    """meaning_detail이 빈 단어 목록 수집"""
    results = []
    for path in sorted(ANALYSIS_CACHE.glob("*.json")):
        if path.suffix != ".json" or path.name.endswith(".bak"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        track = data.get("track", path.stem)
        for si, s in enumerate(data.get("analyses", [])):
            for wi, w in enumerate(s.get("words", [])):
                if not w.get("meaning_detail", ""):
                    results.append(
                        {
                            "file": str(path),
                            "track": track,
                            "sentence_idx": si,
                            "word_idx": wi,
                            "word": w["word"],
                            "pinyin": w.get("pinyin", ""),
                            "meaning_ko": w.get("meaning_ko", ""),
                            "part_of_speech": w.get("part_of_speech", ""),
                        }
                    )
    return results


def batch_fill_details(entries: list[dict], client: OpenAI, batch_size: int = 50) -> dict:
    """GPT로 meaning_detail 일괄 생성. Returns: {(file, si, wi): detail_text}"""
    results = {}

    for i in range(0, len(entries), batch_size):
        batch = entries[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(entries) + batch_size - 1) // batch_size
        print(f"  배치 {batch_num}/{total_batches} ({len(batch)}개 단어)...")

        prompt = "다음 중국어 단어들의 상세 설명(meaning_detail)을 작성해 주세요.\n"
        prompt += "각 단어에 대해 용법, 뉘앙스, 비슷한 단어와의 차이점을 한국어로 설명해 주세요.\n"
        prompt += 'JSON 배열로 응답하세요: [{"idx": 0, "detail": "설명"}, ...]\n\n'

        for j, e in enumerate(batch):
            prompt += (
                f"{j}. {e['word']} ({e['pinyin']}) - {e['meaning_ko']} [{e['part_of_speech']}]\n"
            )

        try:
            response = client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "중국어 교육 전문가입니다. 한국인 학습자를 위해 단어 설명을 작성합니다.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=1,
                timeout=120,
            )

            content = json.loads(response.choices[0].message.content)

            # GPT 응답 형태: list, {"results":[...]}, {"0":{...},"1":{...}} 등
            if isinstance(content, list):
                items = content
            elif isinstance(content, dict):
                # {"results": [...]} 또는 {"words": [...]} 형태
                for key in ("results", "words", "data"):
                    if key in content and isinstance(content[key], list):
                        items = content[key]
                        break
                else:
                    # {"0": {"idx":0, "detail":"..."}, "1": {...}} 형태
                    items = list(content.values())
            else:
                items = []

            for item in items:
                if not isinstance(item, dict):
                    continue
                idx = item.get("idx", -1)
                detail = item.get("detail", "")
                if 0 <= idx < len(batch) and detail:
                    e = batch[idx]
                    key = (e["file"], e["sentence_idx"], e["word_idx"])
                    results[key] = detail

        except Exception as ex:
            print(f"    ⚠ API 오류: {ex}")

        if i + batch_size < len(entries):
            time.sleep(1)

    return results


def apply_details(details: dict):
    """캐시 파일에 meaning_detail 반영"""
    # 파일별로 그룹화
    by_file: dict[str, list] = {}
    for (file, si, wi), detail in details.items():
        if file not in by_file:
            by_file[file] = []
        by_file[file].append((si, wi, detail))

    for file, updates in by_file.items():
        path = __import__("pathlib").Path(file)
        data = json.loads(path.read_text(encoding="utf-8"))
        for si, wi, detail in updates:
            data["analyses"][si]["words"][wi]["meaning_detail"] = detail

        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  {len(by_file)}개 파일 업데이트 완료")


def main():
    parser = argparse.ArgumentParser(description="빈 meaning_detail GPT 보충")
    parser.add_argument("--dry-run", action="store_true", help="대상 목록만 출력")
    args = parser.parse_args()

    entries = collect_empty_details()
    print(f"빈 meaning_detail: {len(entries)}건")

    if not entries:
        print("보충할 항목 없음.")
        return

    if args.dry_run:
        for e in entries[:20]:
            print(f"  {e['track']:12s} {e['word']:8s} {e['meaning_ko']}")
        if len(entries) > 20:
            print(f"  ... 외 {len(entries) - 20}건")
        print("\n[DRY RUN] GPT 호출 없음. --dry-run 없이 실행하세요.")
        return

    client = OpenAI()
    print(f"GPT 모델: {GPT_MODEL}")
    details = batch_fill_details(entries, client)
    print(f"생성된 설명: {len(details)}건 / {len(entries)}건")

    if details:
        apply_details(details)
    print("완료.")


if __name__ == "__main__":
    main()
