"""models.py 테스트 — to_dict/from_dict 라운드트립, 운영 규모 검증"""

import pytest

from models import (
    GrammarPoint,
    SentenceAnalysis,
    TrackAnalysis,
    WordBreakdown,
)


class TestWordBreakdown:
    def test_fields(self):
        w = WordBreakdown(
            word="你好",
            pinyin="nǐ hǎo",
            part_of_speech="감탄사",
            meaning_ko="안녕하세요",
            meaning_detail="인사말",
        )
        assert w.word == "你好"
        assert w.pinyin == "nǐ hǎo"
        assert w.meaning_ko == "안녕하세요"


class TestGrammarPoint:
    def test_fields(self):
        g = GrammarPoint(
            pattern="因为...所以...",
            explanation_ko="...이기 때문에 ...이다",
            example="因为下雨，所以我没去。",
        )
        assert g.pattern == "因为...所以..."


class TestTrackAnalysisRoundtrip:
    def test_basic_roundtrip(self, sample_track):
        """기본 직렬화/역직렬화 라운드트립"""
        d = sample_track.to_dict()
        restored = TrackAnalysis.from_dict(d)

        assert restored.track_name == sample_track.track_name
        assert restored.source_path == sample_track.source_path
        assert restored.transcription == sample_track.transcription
        assert len(restored.sentences) == len(sample_track.sentences)

        s_orig = sample_track.sentences[0]
        s_rest = restored.sentences[0]
        assert s_rest.original == s_orig.original
        assert s_rest.pinyin_full == s_orig.pinyin_full
        assert s_rest.translation_ko == s_orig.translation_ko
        assert s_rest.role == s_orig.role

    def test_words_roundtrip(self, sample_track):
        d = sample_track.to_dict()
        restored = TrackAnalysis.from_dict(d)
        w = restored.sentences[0].words[0]
        assert w.word == "学习"
        assert w.pinyin == "xué xí"
        assert w.part_of_speech == "동사"
        assert w.meaning_detail == "체계적으로 배우다"

    def test_grammar_roundtrip(self, sample_track):
        d = sample_track.to_dict()
        restored = TrackAnalysis.from_dict(d)
        g = restored.sentences[0].grammar_points[0]
        assert g.pattern == "虽然...但是..."
        assert "비록" in g.explanation_ko

    def test_optional_role_default(self):
        """role 필드 없으면 빈 문자열"""
        d = {
            "track_name": "TEST",
            "source_path": "test.mp3",
            "transcription": "你好",
            "sentences": [
                {
                    "sentence_index": 0,
                    "original": "你好",
                    "pinyin_full": "nǐ hǎo",
                    "words": [],
                    "grammar_points": [],
                    "translation_ko": "안녕",
                    "translation_literal_ko": "안녕",
                    "difficulty_note": "",
                }
            ],
        }
        track = TrackAnalysis.from_dict(d)
        assert track.sentences[0].role == ""

    def test_operational_scale_100_sentences(self, sample_sentence):
        """운영 규모 테스트 — 100+ 문장 라운드트립"""
        sentences = []
        for i in range(150):
            s = SentenceAnalysis(
                sentence_index=i,
                original=f"测试句子{i}。",
                pinyin_full=f"cè shì jù zi {i}",
                words=[
                    WordBreakdown(
                        word=f"测试{i}",
                        pinyin="cè shì",
                        part_of_speech="명사",
                        meaning_ko=f"테스트{i}",
                        meaning_detail="",
                    )
                ],
                grammar_points=[],
                translation_ko=f"테스트 문장 {i}",
                translation_literal_ko=f"테스트 문장 {i}",
                difficulty_note="",
                role="나레이터" if i % 2 == 0 else "화자A",
            )
            sentences.append(s)

        track = TrackAnalysis(
            track_name="SCALE_TEST",
            source_path="test.mp3",
            transcription="x" * 5000,
            sentences=sentences,
            total_duration_hint="10:00",
            processing_timestamp="2026-01-01",
        )

        d = track.to_dict()
        restored = TrackAnalysis.from_dict(d)

        assert len(restored.sentences) == 150
        assert restored.sentences[0].original == "测试句子0。"
        assert restored.sentences[149].original == "测试句子149。"
        assert restored.sentences[50].role == "나레이터"
        assert restored.sentences[51].role == "화자A"

    def test_real_data_roundtrip(self, real_analysis_data):
        """실제 캐시 데이터로 라운드트립"""
        if real_analysis_data is None:
            pytest.skip("fixture 파일 없음")

        analyses = real_analysis_data.get("analyses", [])
        assert len(analyses) > 0, "분석 데이터가 비어있음"

        # TrackAnalysis 구성
        sentences = []
        for s in analyses:
            words = [WordBreakdown(**w) for w in s.get("words", [])]
            grammar = [GrammarPoint(**g) for g in s.get("grammar_points", [])]
            sentences.append(
                SentenceAnalysis(
                    sentence_index=s["sentence_index"],
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

        track = TrackAnalysis(
            track_name="TRACK001",
            source_path="test.mp3",
            transcription="test",
            sentences=sentences,
            total_duration_hint="",
            processing_timestamp="test",
        )

        d = track.to_dict()
        restored = TrackAnalysis.from_dict(d)
        assert len(restored.sentences) == len(sentences)

        for orig, rest in zip(sentences, restored.sentences):
            assert orig.original == rest.original
            assert orig.pinyin_full == rest.pinyin_full
            assert len(orig.words) == len(rest.words)
