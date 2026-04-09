"""render_only.py - 캐시에서 로드하여 HTML만 재생성

분석(GPT/Agent) 없이 기존 캐시 데이터로 HTML을 렌더링합니다.
음성인식이나 API 호출 없이 빠르게 HTML을 재생성할 때 사용합니다.

사용법:
  python render_only.py                    # listening 전체
  python render_only.py --source vocabulary # 단어 MP3
  python render_only.py --range 1 10       # TRACK001~010만
"""

import argparse
import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

from config import ANALYSIS_CACHE, MP3_SOURCES, OUTPUT_DIR, TRANSCRIPTION_CACHE  # noqa: E402
from models import GrammarPoint, SentenceAnalysis, TrackAnalysis, WordBreakdown  # noqa: E402
from renderer import Renderer  # noqa: E402


def load_track_from_cache(track_name: str, source_dir: Path) -> TrackAnalysis:
    """캐시에서 TrackAnalysis 로드"""
    trans_path = TRANSCRIPTION_CACHE / f"{track_name}.json"
    anal_path = ANALYSIS_CACHE / f"{track_name}.json"

    transcription = ""
    if trans_path.exists():
        with open(trans_path, encoding="utf-8") as f:
            transcription = json.load(f).get("text", "")

    sentences = []
    if anal_path.exists():
        with open(anal_path, encoding="utf-8") as f:
            data = json.load(f)
        for s in data.get("analyses", []):
            words = [WordBreakdown(**w) if isinstance(w, dict) else w for w in s.get("words", [])]
            grammar = [
                GrammarPoint(**g) if isinstance(g, dict) else g for g in s.get("grammar_points", [])
            ]
            sentences.append(
                SentenceAnalysis(
                    sentence_index=s.get("sentence_index", 0),
                    original=s["original"],
                    pinyin_full=s["pinyin_full"],
                    words=words,
                    grammar_points=grammar,
                    translation_ko=s["translation_ko"],
                    translation_literal_ko=s["translation_literal_ko"],
                    difficulty_note=s["difficulty_note"],
                    role=s.get("role", ""),
                )
            )

    mp3_path = source_dir / f"{track_name}.mp3"
    return TrackAnalysis(
        track_name=track_name,
        source_path=str(mp3_path),
        transcription=transcription,
        sentences=sentences,
        total_duration_hint="",
        processing_timestamp="cached",
    )


def main():
    parser = argparse.ArgumentParser(description="캐시에서 HTML 재생성")
    parser.add_argument("--source", choices=["listening", "vocabulary"], default="listening")
    parser.add_argument("--range", type=int, nargs=2, metavar=("START", "END"))
    args = parser.parse_args()

    source_dir = MP3_SOURCES[args.source]
    renderer = Renderer()

    # 캐시된 트랙 목록 수집
    track_names = []
    for f in sorted(ANALYSIS_CACHE.glob("TRACK[0-9][0-9][0-9].json")):
        track_names.append(f.stem)

    if args.range:
        start, end = args.range
        track_names = [t for t in track_names if start <= int(t.replace("TRACK", "")) <= end]

    print(f"=== HTML 재생성: {len(track_names)}개 트랙 ({args.source}) ===")

    # 캐시에서 로드
    tracks = []
    for name in track_names:
        t = load_track_from_cache(name, source_dir)
        tracks.append(t)
        print(f"  {name}: {len(t.sentences)}문장")

    if not tracks:
        print("렌더링할 트랙이 없습니다.")
        return

    # 통합 HTML 생성
    combined_path = renderer.render_combined(tracks, args.source)
    print(f"\n통합 HTML: {combined_path}")

    # 개별 HTML 생성
    for t in tracks:
        renderer.render_track(t)
    print(f"개별 HTML: {len(tracks)}개 생성")

    # 분할 트랙 HTML
    split_pages = renderer.render_split_tracks(tracks)
    if split_pages:
        print(f"분할 트랙 HTML: {len(split_pages)}개 생성")

    # 목록 페이지
    index_data = [
        {
            "track_name": t.track_name,
            "filename": f"{t.track_name}.html",
            "success": True,
            "sentence_count": len(t.sentences),
            "source": args.source,
        }
        for t in tracks
    ]
    renderer.render_index(index_data)
    print(f"목록 페이지: {OUTPUT_DIR / 'index.html'}")

    total_sents = sum(len(t.sentences) for t in tracks)
    print(f"\n=== 완료: {len(tracks)}개 트랙, {total_sents}문장 ===")


if __name__ == "__main__":
    main()
