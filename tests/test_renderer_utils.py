"""renderer.py 순수 함수 테스트 — _chinese_to_int, _build_ruby_html"""

import pytest

from models import WordBreakdown
from renderer import _build_ruby_html, _chinese_to_int


class TestChineseToInt:
    @pytest.mark.parametrize(
        "chinese,expected",
        [
            ("一", 1),
            ("二", 2),
            ("三", 3),
            ("四", 4),
            ("五", 5),
            ("六", 6),
            ("七", 7),
            ("八", 8),
            ("九", 9),
            ("十", 10),
            ("十一", 11),
            ("十五", 15),
            ("十九", 19),
            ("二十", 20),
            ("三十", 30),
            ("四十五", 45),
            ("九十九", 99),
        ],
    )
    def test_basic_numbers(self, chinese, expected):
        assert _chinese_to_int(chinese) == expected

    def test_empty_string(self):
        assert _chinese_to_int("") == 0

    def test_all_1_to_99(self):
        """운영 규모 — 1~99 전체 검증"""
        cn_digits = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
        for n in range(1, 100):
            if n <= 9:
                cn = cn_digits[n]
            elif n == 10:
                cn = "十"
            elif n < 20:
                cn = f"十{cn_digits[n % 10]}"
            elif n % 10 == 0:
                cn = f"{cn_digits[n // 10]}十"
            else:
                cn = f"{cn_digits[n // 10]}十{cn_digits[n % 10]}"
            assert _chinese_to_int(cn) == n, f"{cn} → expected {n}, got {_chinese_to_int(cn)}"


class TestBuildRubyHtml:
    def test_basic_match(self):
        words = [
            WordBreakdown(
                word="你好", pinyin="nǐ hǎo", part_of_speech="", meaning_ko="", meaning_detail=""
            ),
        ]
        result = _build_ruby_html("你好。", words)
        assert "<ruby>你好<rt>nǐ hǎo</rt></ruby>" in result
        assert "。" in result  # 구두점 유지

    def test_multiple_words(self):
        words = [
            WordBreakdown(
                word="我", pinyin="wǒ", part_of_speech="", meaning_ko="", meaning_detail=""
            ),
            WordBreakdown(
                word="学习", pinyin="xué xí", part_of_speech="", meaning_ko="", meaning_detail=""
            ),
        ]
        result = _build_ruby_html("我学习。", words)
        assert "<ruby>我<rt>wǒ</rt></ruby>" in result
        assert "<ruby>学习<rt>xué xí</rt></ruby>" in result

    def test_gap_handling(self):
        """GPT가 단어를 누락한 경우 — 갭이 plain text로 출력"""
        words = [
            WordBreakdown(
                word="你好", pinyin="nǐ hǎo", part_of_speech="", meaning_ko="", meaning_detail=""
            ),
        ]
        result = _build_ruby_html("你好世界。", words)
        assert "<ruby>你好<rt>nǐ hǎo</rt></ruby>" in result
        assert "世界。" in result  # 누락분 plain text

    def test_empty_words(self):
        """words 빈 리스트 → original 그대로"""
        result = _build_ruby_html("你好世界", [])
        assert result == "你好世界"

    def test_dict_input(self):
        """dict 형태 words 처리"""
        words = [{"word": "学习", "pinyin": "xué xí"}]
        result = _build_ruby_html("我学习。", words)
        assert "<ruby>学习<rt>xué xí</rt></ruby>" in result

    def test_punctuation_preserved(self):
        """구두점이 모두 보존되는지"""
        words = [
            WordBreakdown(
                word="你好", pinyin="nǐ hǎo", part_of_speech="", meaning_ko="", meaning_detail=""
            ),
        ]
        result = _build_ruby_html("你好！", words)
        assert "！" in result

    def test_operational_scale_many_sentences(self, real_analysis_data):
        """운영 규모 — 실제 분석 데이터로 ruby 생성"""
        if real_analysis_data is None:
            pytest.skip("fixture 파일 없음")

        analyses = real_analysis_data.get("analyses", [])
        assert len(analyses) > 0

        for s in analyses:
            original = s["original"]
            words = [WordBreakdown(**w) for w in s.get("words", [])]
            result = _build_ruby_html(original, words)
            # original의 모든 글자가 결과에 포함되어야 함
            for ch in original:
                assert ch in result, f"'{ch}' missing from ruby HTML of '{original}'"
