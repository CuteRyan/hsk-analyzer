"""공유 픽스처"""

import json
from pathlib import Path

import pytest

from models import (
    GrammarPoint,
    SentenceAnalysis,
    TrackAnalysis,
    WordBreakdown,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_word():
    return WordBreakdown(
        word="学习",
        pinyin="xué xí",
        part_of_speech="동사",
        meaning_ko="공부하다",
        meaning_detail="체계적으로 배우다",
    )


@pytest.fixture
def sample_grammar():
    return GrammarPoint(
        pattern="虽然...但是...",
        explanation_ko="비록 ...이지만 ...이다",
        example="虽然很难，但是我不会放弃。",
    )


@pytest.fixture
def sample_sentence(sample_word, sample_grammar):
    return SentenceAnalysis(
        sentence_index=0,
        original="我喜欢学习中文。",
        pinyin_full="wǒ xǐ huān xué xí zhōng wén",
        words=[sample_word],
        grammar_points=[sample_grammar],
        translation_ko="나는 중국어 공부를 좋아합니다.",
        translation_literal_ko="나 좋아하다 공부하다 중국어",
        difficulty_note="HSK 3급 기본 문장 구조",
        role="나레이터",
    )


@pytest.fixture
def sample_track(sample_sentence):
    return TrackAnalysis(
        track_name="TRACK001",
        source_path="test/TRACK001.mp3",
        transcription="我喜欢学习中文。",
        sentences=[sample_sentence],
        total_duration_hint="00:30",
        processing_timestamp="2026-01-01 00:00",
    )


@pytest.fixture
def real_analysis_data():
    """실제 캐시에서 복사한 analysis JSON"""
    path = FIXTURES_DIR / "sample_analysis.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


@pytest.fixture
def real_transcription_data():
    """실제 캐시에서 복사한 transcription JSON"""
    path = FIXTURES_DIR / "sample_transcription.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None
