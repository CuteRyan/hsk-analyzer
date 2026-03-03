"""models.py - 데이터 클래스 정의"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json


@dataclass
class WordBreakdown:
    """단어별 분석 결과"""
    word: str              # 중국어 단어 (예: "学习")
    pinyin: str            # 병음 (예: "xué xí")
    part_of_speech: str    # 품사 (한국어: 명사/동사/형용사 등)
    meaning_ko: str        # 한국어 뜻 (예: "공부하다")
    meaning_detail: str    # 상세 설명


@dataclass
class GrammarPoint:
    """문법 포인트"""
    pattern: str           # 문법 패턴 (예: "虽然...但是...")
    explanation_ko: str    # 한국어 설명
    example: str           # 예문


@dataclass
class SentenceAnalysis:
    """문장별 분석 결과"""
    sentence_index: int
    original: str                        # 원문 중국어
    pinyin_full: str                     # 전체 병음
    words: List[WordBreakdown]           # 단어별 분석
    grammar_points: List[GrammarPoint]   # 문법 포인트
    translation_ko: str                  # 한국어 번역
    translation_literal_ko: str          # 직역
    difficulty_note: str                 # 학습 팁


@dataclass
class TrackAnalysis:
    """트랙 전체 분석 결과"""
    track_name: str
    source_path: str
    transcription: str
    sentences: List[SentenceAnalysis]
    total_duration_hint: str
    processing_timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'TrackAnalysis':
        sentences = []
        for s in data.get("sentences", []):
            words = [WordBreakdown(**w) for w in s.get("words", [])]
            grammar = [GrammarPoint(**g) for g in s.get("grammar_points", [])]
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
        return cls(
            track_name=data["track_name"],
            source_path=data["source_path"],
            transcription=data["transcription"],
            sentences=sentences,
            total_duration_hint=data.get("total_duration_hint", ""),
            processing_timestamp=data.get("processing_timestamp", ""),
        )
