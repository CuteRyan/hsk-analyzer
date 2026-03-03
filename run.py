"""run.py - HSK 중국어 듣기 분석기 메인 실행 스크립트"""

import argparse
import io
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from dotenv import load_dotenv
load_dotenv(override=True)

from openai import OpenAI

import config
from config import MP3_SOURCES, OUTPUT_DIR
from transcriber import Transcriber
from analyzer import Analyzer
from renderer import Renderer
from cache_manager import CacheManager
from models import TrackAnalysis


def print_progress(msg: str):
    """타임스탬프와 함께 진행 상황 출력"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


def process_single_track(mp3_path: Path, client: OpenAI,
                         cache: CacheManager,
                         force: bool = False) -> TrackAnalysis:
    """단일 MP3 트랙을 처리 (음성인식 → 분석). TrackAnalysis 반환."""
    track_name = mp3_path.stem

    # 캐시 확인
    if not force and cache.is_processed(track_name):
        print_progress(f"  캐시 로드: {track_name}")
        transcription = cache.get_transcription(track_name) or ""
        analyses = cache.get_analysis(track_name) or []
        # SentenceAnalysis 리스트로 복원
        from models import SentenceAnalysis, WordBreakdown, GrammarPoint
        sentences = []
        for s in analyses:
            words = [WordBreakdown(**w) if isinstance(w, dict) else w
                     for w in s.get("words", [])]
            grammar = [GrammarPoint(**g) if isinstance(g, dict) else g
                       for g in s.get("grammar_points", [])]
            sentences.append(SentenceAnalysis(
                sentence_index=s["sentence_index"],
                original=s["original"],
                pinyin_full=s["pinyin_full"],
                words=words,
                grammar_points=grammar,
                translation_ko=s["translation_ko"],
                translation_literal_ko=s["translation_literal_ko"],
                difficulty_note=s["difficulty_note"],
            ))
        return TrackAnalysis(
            track_name=track_name,
            source_path=str(mp3_path),
            transcription=transcription,
            sentences=sentences,
            total_duration_hint="",
            processing_timestamp="cached",
        )

    print_progress(f">> 처리 시작: {track_name}")

    # 1단계: 음성 인식
    print_progress(f"  1/2 음성 인식 중...")
    transcriber = Transcriber(client, cache)
    transcription = transcriber.transcribe_file(mp3_path)
    print_progress(f"  > 인식 완료 ({len(transcription)}자)")

    # 2단계: 문장 분석
    print_progress(f"  2/2 문장 분석 중...")
    analyzer = Analyzer(client, cache)
    analyses = analyzer.analyze_track(track_name, transcription,
                                      progress_callback=print_progress)
    print_progress(f"  > 분석 완료 ({len(analyses)}문장)")

    return TrackAnalysis(
        track_name=track_name,
        source_path=str(mp3_path),
        transcription=transcription,
        sentences=analyses,
        total_duration_hint="",
        processing_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def collect_mp3_files(source_key: str = None) -> list:
    """MP3 파일 목록 수집"""
    if source_key:
        source_dir = MP3_SOURCES.get(source_key)
        if source_dir and source_dir.exists():
            return sorted(source_dir.glob("*.mp3"))
    return sorted(MP3_SOURCES["listening"].glob("*.mp3"))


def main():
    parser = argparse.ArgumentParser(
        description="HSK 중국어 듣기 분석기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python run.py --track TRACK001.mp3          # 단일 트랙 분석
  python run.py --range 1 10                  # TRACK001~010 분석
  python run.py --source vocabulary --all     # 단어 MP3 전체 분석
  python run.py --source listening --all      # 듣기 전체 분석
  python run.py --file "경로/파일.mp3"         # 특정 파일 경로
  python run.py --force --track TRACK001.mp3  # 캐시 무시하고 재분석
  python run.py --model gpt-5-mini --track TRACK001.mp3  # 모델 지정
        """,
    )
    parser.add_argument("--track", type=str,
                        help="단일 트랙 파일명 (예: TRACK001.mp3)")
    parser.add_argument("--file", type=str,
                        help="MP3 파일 전체 경로")
    parser.add_argument("--range", type=int, nargs=2,
                        metavar=("START", "END"),
                        help="트랙 번호 범위 (예: 1 10)")
    parser.add_argument("--all", action="store_true",
                        help="선택된 소스의 전체 트랙 처리")
    parser.add_argument("--source",
                        choices=["listening", "vocabulary"],
                        default="listening",
                        help="MP3 소스 선택 (기본: listening)")
    parser.add_argument("--force", action="store_true",
                        help="캐시 무시하고 재처리")
    parser.add_argument("--model", type=str, default=None,
                        help="GPT 모델 지정 (기본: config.py 설정값)")

    args = parser.parse_args()

    # 초기화
    client = OpenAI()  # OPENAI_API_KEY 환경변수 사용
    cache = CacheManager()
    renderer = Renderer()

    # 모델 오버라이드
    if args.model:
        config.GPT_MODEL = args.model
        print_progress(f"GPT 모델: {args.model}")

    # 처리할 파일 결정
    if args.file:
        files = [Path(args.file)]
    elif args.track:
        source_dir = MP3_SOURCES[args.source]
        files = [source_dir / args.track]
    elif args.range:
        start, end = args.range
        all_files = collect_mp3_files(args.source)
        files = all_files[start - 1:end]
    elif args.all:
        files = collect_mp3_files(args.source)
    else:
        parser.print_help()
        sys.exit(1)

    # 파일 존재 확인
    existing = [f for f in files if f.exists()]
    missing = [f for f in files if not f.exists()]
    if missing:
        for f in missing:
            print_progress(f"⚠ 파일 없음: {f}")
    if not existing:
        print("오류: 처리할 MP3 파일을 찾을 수 없습니다.")
        sys.exit(1)

    files = existing
    print_progress(f"=== HSK 분석기 시작 ===")
    print_progress(f"GPT 모델: {config.GPT_MODEL}")
    print_progress(f"처리 대상: {len(files)}개 파일")
    print()

    # 각 파일 처리
    track_analyses = []
    errors = []
    for i, mp3_path in enumerate(files, 1):
        print_progress(f"[{i}/{len(files)}] {mp3_path.name}")
        try:
            track_data = process_single_track(
                mp3_path, client, cache, force=args.force
            )
            track_analyses.append(track_data)
        except Exception as e:
            print_progress(f"  X 오류: {e}")
            errors.append(mp3_path.stem)
        print()

    # HTML 생성
    if track_analyses:
        # 통합 HTML 생성 (소스별 하나의 페이지)
        combined_path = renderer.render_combined(track_analyses, args.source)
        print_progress(f"> 통합 HTML 생성: {combined_path}")

        # 개별 HTML도 함께 생성
        for t in track_analyses:
            renderer.render_track(t)

        # 목록 페이지
        index_data = []
        for t in track_analyses:
            index_data.append({
                "track_name": t.track_name,
                "filename": f"{t.track_name}.html",
                "success": True,
                "sentence_count": len(t.sentences),
                "source": args.source,
            })
        renderer.render_index(index_data)

    # 요약
    print_progress(f"=== 완료 ===")
    print_progress(f"성공: {len(track_analyses)}/{len(files)}")
    if errors:
        print_progress(f"실패: {', '.join(errors)}")
    if track_analyses:
        print_progress(f"통합 페이지: {OUTPUT_DIR / f'{args.source}.html'}")
        print_progress(f"목록 페이지: {OUTPUT_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
