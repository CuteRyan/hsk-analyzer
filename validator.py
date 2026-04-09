"""validator.py - GPT 출력 검증 + 자동 교정 가드레일"""

import re

from models import SentenceAnalysis

# 품사 정규화 매핑: 중국어 → 한국어
_POS_CN_TO_KR: dict[str, str] = {
    "名词": "명사",
    "动词": "동사",
    "形容词": "형용사",
    "副词": "부사",
    "介词": "전치사",
    "连词": "접속사",
    "助词": "조사",
    "量词": "양사",
    "代词": "대사",
    "感叹词": "감탄사",
    "数词": "수사",
    "助动词": "동사",
    "拟声词": "감탄사",
    "能愿动词": "동사",
    "趋向动词": "동사",
    "判断动词": "동사",
    "时间词": "명사",
    "方位词": "명사",
    "处所词": "명사",
    "区别词": "형용사",
    "数量": "양사",
}

# 비표준 한국어 변종 → 표준값
_POS_KR_NORMALIZE: dict[str, str] = {
    # 대사 계열
    "대명사": "대사",
    "대사": "대사",
    "의문사": "대사",
    "의문대사": "대사",
    "의문대명사": "대사",
    "의문부사": "부사",
    "지시대사": "대사",
    "지시대명사": "대사",
    # 동사 계열
    "조동사": "동사",
    "보조동사": "동사",
    "보어": "동사",
    "결과보어": "동사",
    "방향보어": "동사",
    "가능보어": "동사",
    # 명사 계열
    "수사": "명사",
    "방위사": "명사",
    "고유명사": "명사",
    "관용구": "명사",
    "관용어": "명사",
    "성어": "명사",
    "속담": "명사",
    "인사말": "명사",
    "호칭": "명사",
    "시간": "명사",
    "부정사": "명사",
    "구성요소": "명사",
    # 형용사 계열
    "관형사": "형용사",
    "관형어": "형용사",
    # 전치사 계열
    "개사": "전치사",
    # 조사 계열
    "어기조사": "조사",
    "동태조사": "조사",
    "구조조사": "조사",
    "어미": "조사",
    # 양사 계열
    "수량사": "양사",
}

# 한국어 "구/문" 접미사 → 핵심 품사 추출
_POS_KR_PHRASE_MAP: dict[str, str] = {
    "동사": "동사",
    "명사": "명사",
    "부사": "부사",
    "형용사": "형용사",
    "전치사": "전치사",
    "접속": "접속사",
    "감탄": "감탄사",
    "의문": "대사",
    "수량": "양사",
    "피동": "동사",
    "연동": "동사",
    "처치": "동사",
    "반문": "대사",
    "시간": "명사",
}

# 표준 품사 목록
VALID_POS = {"명사", "동사", "형용사", "부사", "전치사", "접속사", "조사", "양사", "대사", "감탄사"}

# 표준 역할 목록
VALID_ROLES = {"화자A", "화자B", "화자C", "나레이터", "질문"}


def normalize_part_of_speech(pos: str) -> tuple[str, bool]:
    """품사를 표준 한국어 값으로 정규화.
    Returns: (정규화된 품사, 교정 여부)"""
    if not pos:
        return "기타", True

    stripped = pos.strip()

    # 이미 표준값이면 그대로
    if stripped in VALID_POS or stripped == "기타":
        return stripped, False

    # 중국어 → 한국어 매핑
    if stripped in _POS_CN_TO_KR:
        return _POS_CN_TO_KR[stripped], True

    # 비표준 한국어 변종
    if stripped in _POS_KR_NORMALIZE:
        return _POS_KR_NORMALIZE[stripped], True

    # 복합 품사 (명사/동사, 动词/形容词 등) → 첫 번째 값
    if "/" in stripped:
        first = stripped.split("/")[0].strip()
        result, _ = normalize_part_of_speech(first)
        return result, True

    # 중국어 구(短语, ~短语, ~구) → 핵심 품사 추출
    for cn_key, kr_val in _POS_CN_TO_KR.items():
        if cn_key in stripped:
            return kr_val, True

    # 한국어 구(~구) → 핵심 품사 추출 (정확 매칭 우선)
    for kr_key, kr_val in _POS_KR_NORMALIZE.items():
        if kr_key in stripped:
            return kr_val, True

    # 한국어 "구/문/태" 접미사 패턴 (동사구→동사, 의문구→대사 등)
    if any(stripped.endswith(sfx) for sfx in ("구", "문", "태")):
        for prefix, target in _POS_KR_PHRASE_MAP.items():
            if prefix in stripped:
                return target, True
        return "명사", True  # 단독 "구" 등 → 명사 기본값

    # 괄호 포함 (동사(어근), 명사(시간) 등) → 괄호 앞 부분으로 재귀
    if "(" in stripped or "（" in stripped:
        base = re.split(r"[(\（]", stripped)[0].strip()
        if base:
            result, _ = normalize_part_of_speech(base)
            return result, True

    # "+" 포함 (부사+조동사 등) → 첫 번째 값
    if "+" in stripped:
        first = stripped.split("+")[0].strip()
        result, _ = normalize_part_of_speech(first)
        return result, True

    # 중국어 短语/成语/惯用语 등 → 명사 기본값
    if any(ch in stripped for ch in ("短语", "成语", "惯用语", "插入语", "句型", "补语")):
        return "명사", True

    # 구어표현, 시간표현 등
    if "표현" in stripped:
        return "명사", True

    # 매핑 불가
    return "기타", True


def validate_role(role: str) -> tuple[str, bool]:
    """역할을 표준값으로 정규화.
    Returns: (정규화된 역할, 교정 여부)"""
    if not role:
        return "나레이터", True

    stripped = role.strip()

    if stripped in VALID_ROLES:
        return stripped, False

    # 오타 교정
    if "化" in stripped:
        fixed = stripped.replace("化", "화")
        if fixed in VALID_ROLES:
            return fixed, True

    # 부분 매칭
    for valid in VALID_ROLES:
        if valid in stripped:
            return valid, True

    return "나레이터", True


def check_word_coverage(original: str, words: list) -> float:
    """original 텍스트 대비 words 배열의 커버리지 비율 계산.
    구두점 제외 한자 기준."""
    # 구두점 제거
    clean = re.sub(r"[，。！？!?、；：,.;:\s\"'" "''《》【】（）()]", "", original)
    if not clean:
        return 1.0

    covered = 0
    for w in words:
        word = w.word if hasattr(w, "word") else w.get("word", "")
        word_clean = re.sub(r"[，。！？!?、；：,.;:\s\"'" "''《》【】（）()….]", "", word)
        for ch in word_clean:
            if ch in clean:
                covered += 1

    return min(covered / len(clean), 1.0)


def validate_analysis(analysis: SentenceAnalysis) -> dict:
    """SentenceAnalysis 객체를 검증+교정.
    Returns: 교정 결과 요약 dict"""
    corrections = []
    warnings = []

    # 1. 품사 정규화
    for w in analysis.words:
        normalized, changed = normalize_part_of_speech(w.part_of_speech)
        if changed:
            corrections.append(f"품사: '{w.part_of_speech}' → '{normalized}' ({w.word})")
            w.part_of_speech = normalized

    # 2. 역할 검증
    normalized_role, role_changed = validate_role(analysis.role)
    if role_changed:
        corrections.append(f"역할: '{analysis.role}' → '{normalized_role}'")
        analysis.role = normalized_role

    # 3. 단어 커버리지
    coverage = check_word_coverage(analysis.original, analysis.words)
    if coverage < 0.8:
        warnings.append(f"단어 커버리지 {coverage:.0%} (원문: {analysis.original[:30]}...)")

    # 4. 필수 필드 검증
    if not analysis.pinyin_full:
        warnings.append("pinyin_full 비어있음")
    if not analysis.translation_ko:
        warnings.append("translation_ko 비어있음")

    empty_details = sum(1 for w in analysis.words if not w.meaning_detail)
    if empty_details > 0:
        warnings.append(f"meaning_detail 빈값 {empty_details}건")

    return {
        "corrections": corrections,
        "warnings": warnings,
        "correction_count": len(corrections),
        "warning_count": len(warnings),
    }


def validate_batch(analyses: list[SentenceAnalysis]) -> dict:
    """배치 단위 검증. 전체 통계 반환."""
    total_corrections = 0
    total_warnings = 0
    all_corrections = []
    all_warnings = []

    for a in analyses:
        result = validate_analysis(a)
        total_corrections += result["correction_count"]
        total_warnings += result["warning_count"]
        all_corrections.extend(result["corrections"])
        all_warnings.extend(result["warnings"])

    return {
        "total_corrections": total_corrections,
        "total_warnings": total_warnings,
        "corrections": all_corrections,
        "warnings": all_warnings,
    }
