"""analyzer.py - GPT API로 문장별 상세 분석"""

import json
import math
import re
import time
from typing import List, Callable, Optional
from openai import OpenAI

from models import SentenceAnalysis, WordBreakdown, GrammarPoint
from config import GPT_MODEL, ANALYSIS_BATCH_SIZE, API_DELAY_SECONDS
from cache_manager import CacheManager


# GPT 구조화 출력을 위한 JSON 스키마
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "pinyin_full": {
                        "type": "string",
                        "description": "성조 부호(ā á ǎ à)를 사용한 전체 병음"
                    },
                    "words": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "word": {"type": "string"},
                                "pinyin": {"type": "string"},
                                "part_of_speech": {
                                    "type": "string",
                                    "description": "품사 (명사/동사/형용사/부사/전치사/접속사/조사/양사/대사/감탄사)"
                                },
                                "meaning_ko": {"type": "string"},
                                "meaning_detail": {"type": "string"}
                            },
                            "required": ["word", "pinyin", "part_of_speech",
                                         "meaning_ko", "meaning_detail"],
                            "additionalProperties": False
                        }
                    },
                    "grammar_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "pattern": {"type": "string"},
                                "explanation_ko": {"type": "string"},
                                "example": {"type": "string"}
                            },
                            "required": ["pattern", "explanation_ko", "example"],
                            "additionalProperties": False
                        }
                    },
                    "translation_ko": {"type": "string"},
                    "translation_literal_ko": {
                        "type": "string",
                        "description": "단어 순서대로 직역한 한국어"
                    },
                    "difficulty_note": {
                        "type": "string",
                        "description": "학습 팁이나 주의사항 (한국어)"
                    },
                    "role": {
                        "type": "string",
                        "description": "화자 역할: 화자A/화자B/화자C/나레이터/질문 중 하나"
                    }
                },
                "required": ["original", "pinyin_full", "words", "grammar_points",
                             "translation_ko", "translation_literal_ko", "difficulty_note", "role"],
                "additionalProperties": False
            }
        }
    },
    "required": ["sentences"],
    "additionalProperties": False
}

SYSTEM_PROMPT = """당신은 한국인 학습자를 위한 중국어 전문 교사입니다.
주어진 중국어 문장들을 상세하게 분석해 주세요.

## 컨텍스트
이 텍스트는 **HSK 5급 듣기 시험** 음성을 텍스트로 변환한 것입니다.
HSK 듣기 시험의 구조:
- 각 문제는 **두 화자(남녀)의 대화** 또는 **한 사람의 독백/지문** 뒤에 **시험 질문**이 나옵니다.
- 마지막 문장은 거의 항상 시험 질문입니다 (예: "这段对话最可能发生在什么地方？", "女的是什么意思？", "男的最可能是做什么的？")
- 대화는 보통 화자A → 화자B → (화자A → 화자B) 순서로 교대합니다.

## 분석 규칙
1. **pinyin_full**: 문장 전체의 병음을 성조 부호(ā, á, ǎ, à)와 함께 작성하세요.
2. **words**: 문장을 의미 단위의 단어로 분리하고, 각 단어에 대해:
   - word: 중국어 단어
   - pinyin: 해당 단어의 병음 (성조 부호 포함)
   - part_of_speech: 품사 (명사/동사/형용사/부사/전치사/접속사/조사/양사/대사/감탄사)
   - meaning_ko: 핵심 한국어 뜻
   - meaning_detail: 용법이나 뉘앙스 설명 (한국어). 비슷한 단어와의 차이점이 있으면 포함.
3. **grammar_points**: 문장에서 발견되는 중요 문법 구조:
   - pattern: 문법 패턴 (예: "虽然...但是...")
   - explanation_ko: 문법 설명 (한국어)
   - example: 다른 예문
4. **translation_ko**: 자연스러운 한국어 번역
5. **translation_literal_ko**: 중국어 어순 그대로 직역 (어순 이해 도움)
6. **difficulty_note**: HSK 학습 포인트나 주의사항 (한국어)
7. **role**: 각 문장의 화자 역할을 판별하세요:
   - "화자A": 대화에서 먼저 말하는 화자
   - "화자B": 대화에서 두 번째로 말하는 화자
   - "화자C": 세 번째 이상의 화자 (드문 경우)
   - "나레이터": 상황 설명, 지문, 한 사람의 독백/서술
   - "질문": 시험 문제 (마지막에 나오는 "~是什么意思？", "~最可能在哪儿？" 등)

정확성이 가장 중요합니다. 병음 성조를 정확하게 표기하세요."""


class Analyzer:
    def __init__(self, client: OpenAI, cache: CacheManager):
        self.client = client
        self.cache = cache

    def analyze_track(self, track_name: str, transcription: str,
                      progress_callback: Optional[Callable] = None,
                      force: bool = False) -> List[SentenceAnalysis]:
        """트랙 전체 문장 분석"""
        # 캐시 확인
        if not force:
            cached = self.cache.get_analysis(track_name)
            if cached is not None:
                return self._dicts_to_analyses(cached)

        # 구두점 교정 (FunASR ct-punc가 쉼표만 쓰는 경우)
        if progress_callback:
            progress_callback(f"  구두점 교정 중...")
        fixed = self._fix_punctuation(transcription)
        if fixed != transcription:
            self.cache.save_transcription(track_name, fixed)
            transcription = fixed

        # 문장 분리
        sentences = self._split_sentences(transcription)

        if not sentences:
            return []

        all_analyses = []
        total_batches = math.ceil(len(sentences) / ANALYSIS_BATCH_SIZE)

        for batch_idx in range(0, len(sentences), ANALYSIS_BATCH_SIZE):
            batch = sentences[batch_idx:batch_idx + ANALYSIS_BATCH_SIZE]
            batch_num = batch_idx // ANALYSIS_BATCH_SIZE + 1

            if progress_callback:
                progress_callback(f"  문장 분석 중... ({batch_num}/{total_batches})")

            results = self._analyze_batch(batch, batch_idx)
            all_analyses.extend(results)

            # API 호출 간 대기
            if batch_idx + ANALYSIS_BATCH_SIZE < len(sentences):
                time.sleep(API_DELAY_SECONDS)

        # 캐시 저장
        self.cache.save_analysis(track_name, all_analyses)
        return all_analyses

    def _fix_punctuation(self, text: str) -> str:
        """GPT로 문장 종결 부호 교정 (，→。？！)"""
        # 이미 종결 부호가 충분하면 스킵
        endings = len(re.findall(r'[。！？!?]', text))
        chars = len(re.sub(r'\s', '', text))
        if chars < 10 or (endings >= 2 and endings >= chars / 30):
            return text

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=GPT_MODEL,
                    messages=[
                        {"role": "system", "content": (
                            "중국어 텍스트의 문장 부호만 교정하세요.\n"
                            "규칙:\n"
                            "1. 쉼표(，) 중 문장이 끝나는 곳을 종결 부호로 바꾸세요: 서술문→。 의문문→？ 감탄문→！\n"
                            "2. 문장 중간의 쉼표(，)는 유지하세요.\n"
                            "3. 글자는 절대 추가/삭제/변경하지 마세요. 구두점만 교정하세요.\n"
                            "4. 교정된 텍스트만 출력하세요. 설명 없이."
                        )},
                        {"role": "user", "content": text}
                    ],
                    temperature=1,
                    timeout=60,
                )
                result = response.choices[0].message.content.strip()

                # 검증: 한자 내용이 동일한지 확인
                orig_chars = re.sub(r'[，。！？!?,.\s、；;：:]', '', text)
                result_chars = re.sub(r'[，。！？!?,.\s、；;：:]', '', result)
                if orig_chars != result_chars:
                    return text  # GPT가 내용을 변경했으면 원본 유지

                return result
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(attempt * 3)
                else:
                    return text  # 실패 시 원본 유지

    def _split_sentences(self, text: str) -> List[str]:
        """중국어 문장 부호 기준으로 분리 (영문/중문 구두점 모두 처리)"""
        # 중국어 + 영문 문장 종결 부호 모두 처리
        sentences = re.split(r'(?<=[。！？!?])\s*', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # HSK 시험 구조 마커 패턴 (제거 대상)
        marker_pattern = re.compile(
            r'^('
            r'第[一二三四五六七八九十\d]+部分[,.，。\s]*'  # 第一部分, 第2部分
            r'|第[一二三四五六七八九十\d]+[题題][,.，。\s]*'  # 第一题, 第3题
            r'|第[一二三四五六七八九十\d]+到第[一二三四五六七八九十\d]+[题題][,.，。\s]*'  # 第1到第5题
            r'|第[一二三四五六七八九十\d]+段[,.，。\s]*'  # 第一段
            r'|[一二三四五六七八九十]+[、.,\s]+'  # 一、 二、
            r'|\d+[、.,\s]+'  # 1、 2.
            r'|听力[,.，。\s]*'  # 听力
            r'|阅读[,.，。\s]*'  # 阅读
            r'|书写[,.，。\s]*'  # 书写
            r')*'
        )

        result = []
        for s in sentences:
            # 마커 제거
            cleaned = marker_pattern.sub('', s).strip()
            if len(cleaned) <= 1:
                continue
            # 중복 문장 제거 (Whisper가 반복 인식하는 경우)
            if result and cleaned == result[-1]:
                continue
            result.append(cleaned)
        return result

    def _analyze_batch(self, sentences: List[str],
                       start_index: int) -> List[SentenceAnalysis]:
        """문장 배치를 GPT API로 분석"""
        user_content = "다음 중국어 문장들을 분석해 주세요:\n\n"
        for i, s in enumerate(sentences):
            user_content += f"{start_index + i + 1}. {s}\n"

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=GPT_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "sentence_analysis",
                            "strict": True,
                            "schema": ANALYSIS_SCHEMA
                        }
                    },
                    temperature=1,
                    timeout=300,
                )
                break
            except Exception as e:
                if attempt < max_retries:
                    wait = attempt * 5
                    print(f"    ⚠ API 오류 (시도 {attempt}/{max_retries}): {e}")
                    print(f"    {wait}초 후 재시도...")
                    time.sleep(wait)
                else:
                    raise RuntimeError(f"API 호출 {max_retries}회 실패: {e}")

        result = json.loads(response.choices[0].message.content)

        analyses = []
        for i, item in enumerate(result["sentences"]):
            analysis = SentenceAnalysis(
                sentence_index=start_index + i,
                original=item["original"],
                pinyin_full=item["pinyin_full"],
                words=[WordBreakdown(**w) for w in item["words"]],
                grammar_points=[GrammarPoint(**g) for g in item["grammar_points"]],
                translation_ko=item["translation_ko"],
                translation_literal_ko=item["translation_literal_ko"],
                difficulty_note=item["difficulty_note"],
                role=item.get("role", ""),
            )
            analyses.append(analysis)

        return analyses

    def _dicts_to_analyses(self, dicts: List[dict]) -> List[SentenceAnalysis]:
        """캐시된 dict 리스트를 SentenceAnalysis 객체로 변환"""
        analyses = []
        for d in dicts:
            analyses.append(SentenceAnalysis(
                sentence_index=d["sentence_index"],
                original=d["original"],
                pinyin_full=d["pinyin_full"],
                words=[WordBreakdown(**w) for w in d["words"]],
                grammar_points=[GrammarPoint(**g) for g in d["grammar_points"]],
                translation_ko=d["translation_ko"],
                translation_literal_ko=d["translation_literal_ko"],
                difficulty_note=d["difficulty_note"],
                role=d.get("role", ""),
            ))
        return analyses
