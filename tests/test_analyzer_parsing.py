"""analyzer.py 파싱 로직 테스트 — _split_sentences (API 호출 없음)"""

from unittest.mock import MagicMock

import pytest

from analyzer import Analyzer


@pytest.fixture
def analyzer():
    """GPT/캐시 없이 Analyzer 인스턴스 생성"""
    mock_client = MagicMock()
    mock_cache = MagicMock()
    return Analyzer(mock_client, mock_cache)


class TestSplitSentences:
    def test_basic_split(self, analyzer):
        result = analyzer._split_sentences("你好。我是中国人。你叫什么名字？")
        assert result == ["你好。", "我是中国人。", "你叫什么名字？"]

    def test_exclamation(self, analyzer):
        result = analyzer._split_sentences("太好了！我很高兴！")
        assert result == ["太好了！", "我很高兴！"]

    def test_english_punctuation(self, analyzer):
        result = analyzer._split_sentences("你好!我是学生.")
        assert "你好!" in result

    def test_marker_removal_part(self, analyzer):
        """HSK 파트 마커 제거"""
        result = analyzer._split_sentences("第一部分 你好。")
        assert len(result) == 1
        assert "第一部分" not in result[0]
        assert "你好" in result[0]

    def test_marker_removal_question(self, analyzer):
        """HSK 문제 마커 제거"""
        result = analyzer._split_sentences("第一题 今天天气怎么样？")
        assert len(result) == 1
        assert "第一题" not in result[0]

    def test_single_char_filter(self, analyzer):
        """1글자(구두점 포함 2글자 이하) 문장 필터링 — 실제 로직은 cleaned 기준 len<=1"""
        result = analyzer._split_sentences("好。你呢？")
        # "好。" → cleaned "好。" len=2 > 1 → 유지됨 (구두점 포함 길이)
        # "你呢？" → cleaned "你呢？" len=3 > 1 → 유지됨
        assert "你呢？" in result
        # 진짜 1글자 입력은 필터링됨
        result2 = analyzer._split_sentences("好")
        assert result2 == []

    def test_duplicate_removal(self, analyzer):
        """중복 문장 제거"""
        result = analyzer._split_sentences("你好。你好。我好。")
        assert result.count("你好。") == 1

    def test_empty_text(self, analyzer):
        result = analyzer._split_sentences("")
        assert result == []

    def test_no_punctuation(self, analyzer):
        """구두점 없는 텍스트"""
        result = analyzer._split_sentences("你好世界")
        assert len(result) >= 1

    def test_real_transcription(self, analyzer, real_transcription_data):
        """운영 규모 — 실제 transcription으로 문장 분리"""
        if real_transcription_data is None:
            pytest.skip("fixture 파일 없음")

        text = real_transcription_data.get("text", "")
        if not text:
            pytest.skip("transcription 텍스트 없음")

        result = analyzer._split_sentences(text)
        assert len(result) > 0, "문장이 하나도 분리되지 않음"
        # 빈 문장 없어야 함
        assert all(len(s.strip()) > 0 for s in result)
        # 1글자 문장 없어야 함
        for s in result:
            cleaned = s.rstrip("。！？!?.")
            assert len(cleaned) > 1, f"1글자 문장 발견: {s}"
