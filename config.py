"""config.py - 설정값 관리"""

import os
from pathlib import Path

# 프로젝트 디렉토리
PROJECT_DIR = Path(__file__).parent

# MP3 소스 디렉토리
MP3_SOURCES = {
    "listening": Path(r"c:/Users/rlgns/OneDrive/문서/HSK/신HSK_한권으로_합격하기5급_개정판/MP3"),
    "vocabulary": Path(r"c:/Users/rlgns/OneDrive/문서/HSK/신HSK_한권으로_합격하기5급_개정판/단어MP3"),
}

# 소스별 한글 이름
SOURCE_LABELS = {
    "listening": "듣기",
    "vocabulary": "단어",
}

# 출력 디렉토리
OUTPUT_DIR = PROJECT_DIR / "output"
CACHE_DIR = PROJECT_DIR / "cache"
TRANSCRIPTION_CACHE = CACHE_DIR / "transcriptions"
ANALYSIS_CACHE = CACHE_DIR / "analyses"
TEMPLATES_DIR = PROJECT_DIR / "templates"

# API 설정
GPT_MODEL = "gpt-5-mini"  # gpt-5-mini, gpt-4.1-nano 등으로 변경 가능

# 분석 배치 크기: GPT 한 번 호출에 보낼 문장 수
ANALYSIS_BATCH_SIZE = 5

# API 호출 간 대기 시간 (초)
API_DELAY_SECONDS = 0.5
