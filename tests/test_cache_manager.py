"""cache_manager.py 테스트 — tmp_path로 격리, 운영 규모 검증"""

import pytest

from models import SentenceAnalysis, WordBreakdown


class TestCacheManager:
    @pytest.fixture(autouse=True)
    def setup_cache(self, tmp_path, monkeypatch):
        """모든 테스트에서 임시 디렉토리 사용"""
        monkeypatch.setattr("cache_manager.TRANSCRIPTION_CACHE", tmp_path / "trans")
        monkeypatch.setattr("cache_manager.ANALYSIS_CACHE", tmp_path / "analysis")

        from cache_manager import CacheManager

        self.cm = CacheManager()
        self.tmp_path = tmp_path

    def test_save_and_get_transcription(self):
        self.cm.save_transcription("TRACK001", "你好世界")
        result = self.cm.get_transcription("TRACK001")
        assert result == "你好世界"

    def test_get_nonexistent_transcription(self):
        assert self.cm.get_transcription("NONEXISTENT") is None

    def test_save_and_get_analysis(self):
        analyses = [
            SentenceAnalysis(
                sentence_index=0,
                original="你好",
                pinyin_full="nǐ hǎo",
                words=[
                    WordBreakdown(
                        word="你好",
                        pinyin="nǐ hǎo",
                        part_of_speech="감탄사",
                        meaning_ko="안녕하세요",
                        meaning_detail="인사말",
                    )
                ],
                grammar_points=[],
                translation_ko="안녕하세요",
                translation_literal_ko="안녕하세요",
                difficulty_note="",
                role="나레이터",
            )
        ]
        self.cm.save_analysis("TRACK001", analyses)
        result = self.cm.get_analysis("TRACK001")
        assert result is not None
        assert len(result) == 1
        assert result[0]["original"] == "你好"

    def test_get_nonexistent_analysis(self):
        assert self.cm.get_analysis("NONEXISTENT") is None

    def test_is_processed_both_exist(self):
        self.cm.save_transcription("T1", "text")
        self.cm.save_analysis("T1", [{"sentence_index": 0, "original": "x"}])
        assert self.cm.is_processed("T1") is True

    def test_is_processed_only_transcription(self):
        self.cm.save_transcription("T2", "text")
        assert self.cm.is_processed("T2") is False

    def test_is_processed_neither(self):
        assert self.cm.is_processed("T3") is False

    def test_utf8_chinese_characters(self):
        """중국어 문자 인코딩 정확성"""
        text = "我喜欢学习中文。你呢？这有什么呀？这样的事，我见多了。"
        self.cm.save_transcription("UTF8_TEST", text)
        result = self.cm.get_transcription("UTF8_TEST")
        assert result == text

    def test_operational_scale_100_tracks(self):
        """운영 규모 — 100+ 트랙 저장/조회"""
        for i in range(120):
            track_name = f"TRACK{i:03d}"
            self.cm.save_transcription(track_name, f"文本{i}")
            self.cm.save_analysis(track_name, [{"sentence_index": 0, "original": f"句子{i}"}])

        # 전부 조회 가능한지 확인
        for i in range(120):
            track_name = f"TRACK{i:03d}"
            assert self.cm.get_transcription(track_name) == f"文本{i}"
            assert self.cm.is_processed(track_name) is True

        # JSON 내용 검증
        result = self.cm.get_analysis("TRACK050")
        assert result[0]["original"] == "句子50"
