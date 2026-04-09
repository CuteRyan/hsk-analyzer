"""validator.py 테스트 — 품사 정규화, 역할 검증, 커버리지 계산"""

import json
from pathlib import Path

import pytest

from models import GrammarPoint, SentenceAnalysis, WordBreakdown
from validator import (
    VALID_POS,
    VALID_ROLES,
    check_word_coverage,
    normalize_part_of_speech,
    validate_analysis,
    validate_batch,
    validate_role,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestNormalizePartOfSpeech:
    @pytest.mark.parametrize(
        "input_pos,expected",
        [
            ("명사", "명사"),
            ("동사", "동사"),
            ("형용사", "형용사"),
            ("부사", "부사"),
            ("전치사", "전치사"),
            ("접속사", "접속사"),
            ("조사", "조사"),
            ("양사", "양사"),
            ("대사", "대사"),
            ("감탄사", "감탄사"),
        ],
    )
    def test_valid_korean_unchanged(self, input_pos, expected):
        result, changed = normalize_part_of_speech(input_pos)
        assert result == expected
        assert changed is False

    @pytest.mark.parametrize(
        "chinese,expected_kr",
        [
            ("名词", "명사"),
            ("动词", "동사"),
            ("形容词", "형용사"),
            ("副词", "부사"),
            ("介词", "전치사"),
            ("连词", "접속사"),
            ("助词", "조사"),
            ("量词", "양사"),
            ("代词", "대사"),
            ("感叹词", "감탄사"),
        ],
    )
    def test_chinese_to_korean(self, chinese, expected_kr):
        result, changed = normalize_part_of_speech(chinese)
        assert result == expected_kr
        assert changed is True

    @pytest.mark.parametrize(
        "variant,expected",
        [
            ("대명사", "대사"),
            ("개사", "전치사"),
            ("조동사", "동사"),
            ("고유명사", "명사"),
            ("관형사", "형용사"),
            ("수사", "명사"),
            ("방위사", "명사"),
            ("助动词", "동사"),
        ],
    )
    def test_nonstandard_variants(self, variant, expected):
        result, changed = normalize_part_of_speech(variant)
        assert result == expected
        assert changed is True

    def test_compound_slash(self):
        result, changed = normalize_part_of_speech("명사/동사")
        assert result in VALID_POS
        assert changed is True

    def test_chinese_phrase(self):
        result, changed = normalize_part_of_speech("动词短语")
        assert result == "동사"
        assert changed is True

    def test_empty_string(self):
        result, changed = normalize_part_of_speech("")
        assert result == "기타"
        assert changed is True

    def test_unmappable(self):
        result, changed = normalize_part_of_speech("알수없음XYZ")
        assert result == "기타"
        assert changed is True

    def test_all_results_in_valid_set(self):
        """모든 결과가 VALID_POS + '기타'에 속해야 함"""
        test_inputs = [
            "名词",
            "动词",
            "形容词",
            "副词",
            "介词",
            "连词",
            "助词",
            "量词",
            "代词",
            "感叹词",
            "명사",
            "동사",
            "형용사",
            "부사",
            "전치사",
            "접속사",
            "조사",
            "양사",
            "대사",
            "감탄사",
            "대명사",
            "개사",
            "조동사",
            "고유명사",
            "관형사",
            "수사",
            "방위사",
            "助动词",
            "动词短语",
            "名词短语",
            "介词短语",
            "명사/동사",
            "동사/형용사",
            "",
            "알수없음",
        ]
        valid_set = VALID_POS | {"기타"}
        for inp in test_inputs:
            result, _ = normalize_part_of_speech(inp)
            assert result in valid_set, f"'{inp}' → '{result}' not in valid set"


class TestValidateRole:
    @pytest.mark.parametrize("role", ["화자A", "화자B", "화자C", "나레이터", "질문"])
    def test_valid_roles_unchanged(self, role):
        result, changed = validate_role(role)
        assert result == role
        assert changed is False

    def test_typo_correction(self):
        result, changed = validate_role("化자A")
        assert result == "화자A"
        assert changed is True

    def test_empty_defaults_to_narrator(self):
        result, changed = validate_role("")
        assert result == "나레이터"
        assert changed is True

    def test_unknown_defaults_to_narrator(self):
        result, changed = validate_role("알수없음")
        assert result == "나레이터"
        assert changed is True


class TestCheckWordCoverage:
    def test_full_coverage(self):
        words = [
            WordBreakdown(
                word="你好", pinyin="", part_of_speech="", meaning_ko="", meaning_detail=""
            ),
            WordBreakdown(
                word="世界", pinyin="", part_of_speech="", meaning_ko="", meaning_detail=""
            ),
        ]
        cov = check_word_coverage("你好世界。", words)
        assert cov >= 0.99

    def test_partial_coverage(self):
        words = [
            WordBreakdown(
                word="你好", pinyin="", part_of_speech="", meaning_ko="", meaning_detail=""
            ),
        ]
        cov = check_word_coverage("你好世界。", words)
        assert 0.4 <= cov <= 0.6

    def test_empty_words(self):
        cov = check_word_coverage("你好", [])
        assert cov == 0.0

    def test_empty_original(self):
        cov = check_word_coverage("", [])
        assert cov == 1.0


class TestValidateAnalysis:
    def _make_analysis(self, pos="名词", role="화자A", original="你好世界。"):
        return SentenceAnalysis(
            sentence_index=0,
            original=original,
            pinyin_full="nǐ hǎo shì jiè",
            words=[
                WordBreakdown(
                    word="你好",
                    pinyin="nǐ hǎo",
                    part_of_speech=pos,
                    meaning_ko="안녕",
                    meaning_detail="인사",
                ),
                WordBreakdown(
                    word="世界",
                    pinyin="shì jiè",
                    part_of_speech=pos,
                    meaning_ko="세계",
                    meaning_detail="세상",
                ),
            ],
            grammar_points=[],
            translation_ko="안녕 세계",
            translation_literal_ko="안녕 세계",
            difficulty_note="",
            role=role,
        )

    def test_corrects_chinese_pos(self):
        a = self._make_analysis(pos="名词")
        result = validate_analysis(a)
        assert result["correction_count"] >= 2
        assert a.words[0].part_of_speech == "명사"

    def test_corrects_role_typo(self):
        a = self._make_analysis(role="化자B")
        result = validate_analysis(a)
        assert a.role == "화자B"
        assert result["correction_count"] >= 1

    def test_warns_low_coverage(self):
        a = self._make_analysis(original="这是一个非常复杂的长句子，包含很多词汇。")
        result = validate_analysis(a)
        assert result["warning_count"] >= 1

    def test_no_issues_clean_data(self):
        a = self._make_analysis(pos="명사", role="화자A")
        result = validate_analysis(a)
        assert result["correction_count"] == 0


class TestValidateBatch:
    def test_operational_scale_real_data(self):
        """운영 규모 — 실제 캐시 데이터 전체 검증"""
        path = FIXTURES_DIR / "sample_analysis.json"
        if not path.exists():
            pytest.skip("fixture 파일 없음")

        data = json.loads(path.read_text(encoding="utf-8"))
        analyses_raw = data.get("analyses", [])
        assert len(analyses_raw) > 0

        analyses = []
        for s in analyses_raw:
            analyses.append(
                SentenceAnalysis(
                    sentence_index=s["sentence_index"],
                    original=s["original"],
                    pinyin_full=s["pinyin_full"],
                    words=[WordBreakdown(**w) for w in s.get("words", [])],
                    grammar_points=[GrammarPoint(**g) for g in s.get("grammar_points", [])],
                    translation_ko=s["translation_ko"],
                    translation_literal_ko=s["translation_literal_ko"],
                    difficulty_note=s["difficulty_note"],
                    role=s.get("role", ""),
                )
            )

        validate_batch(analyses)

        # 검증 후 모든 품사가 표준값이어야 함
        valid_set = VALID_POS | {"기타"}
        for a in analyses:
            for w in a.words:
                assert (
                    w.part_of_speech in valid_set
                ), f"'{w.part_of_speech}' not normalized for word '{w.word}'"

        # 모든 역할이 표준값이어야 함
        for a in analyses:
            assert a.role in VALID_ROLES, f"'{a.role}' not in VALID_ROLES"
