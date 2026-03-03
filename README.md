# HSK 중국어 듣기 분석기

HSK 시험 대비 MP3 음원을 자동으로 인식하고, 문장 하나하나를 **병음 / 단어 분석 / 문법 해설 / 한국어 번역**까지 상세하게 분석해주는 도구입니다.

## 주요 기능

- **음성 인식 (STT)**: OpenAI Whisper API로 중국어 음원을 텍스트로 변환
- **문장별 상세 분석**: GPT API로 각 문장의 병음, 단어, 문법, 번역을 자동 분석
- **통합 HTML 페이지**: 소스별로 전체 트랙을 하나의 HTML에 통합 (사이드바 네비게이션)
- **오디오 플레이어**: 분석 페이지에서 바로 음원 재생 (배속 조절, 되감기)
- **캐싱**: 한 번 분석한 트랙은 캐시하여 API 비용 절약
- **시험 마커 자동 제거**: "第一部分", "第3题" 등 시험 구조 안내문 자동 필터링
- **바로가기**: 배치 파일 + 바탕화면 바로가기로 원클릭 실행

## 분석 결과 예시

각 문장에 대해 다음 정보를 제공합니다:

| 항목 | 설명 |
|------|------|
| 루비 병음 | 한자 위에 병음 표시 (ruby annotation) |
| 전체 병음 | 문장 전체의 병음 (성조 부호 포함) |
| 단어 분석 | 단어별 병음, 품사, 한국어 뜻, 상세 설명 |
| 문법 포인트 | 문장에 포함된 문법 구조 해설 + 예문 |
| 한국어 번역 | 자연스러운 번역 + 어순 이해를 위한 직역 |
| 학습 팁 | HSK 급수별 학습 포인트 |

## 설치

### 1. 저장소 클론

```bash
git clone https://github.com/CuteRyan/hsk-analyzer.git
cd hsk-analyzer
```

### 2. 가상환경 생성 및 패키지 설치

```bash
python -m venv venv

# Windows
source venv/Scripts/activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. API 키 설정

`.env.example`을 복사하여 `.env` 파일을 만들고, OpenAI API 키를 입력합니다.

```bash
cp .env.example .env
```

```ini
# .env
OPENAI_API_KEY=sk-your-api-key-here
```

### 4. (선택) ffmpeg 설치

25MB 초과 MP3 파일 처리 시 필요합니다.

```bash
# Windows
winget install ffmpeg

# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg
```

## 사용법

### CLI (터미널)

```bash
# 가상환경 활성화
source venv/Scripts/activate  # Windows
source venv/bin/activate      # macOS/Linux

# 단일 트랙 분석
python run.py --track TRACK001.mp3

# 트랙 범위 분석 (TRACK001 ~ TRACK010)
python run.py --source listening --range 1 10

# 듣기 전체 분석 (100트랙)
python run.py --source listening --all

# 단어 MP3 전체 분석 (2500개)
python run.py --source vocabulary --all

# 단어 일부 분석
python run.py --source vocabulary --range 1 50

# GPT 모델 변경
python run.py --model gpt-4o-mini --track TRACK001.mp3

# 캐시 무시하고 재분석
python run.py --force --track TRACK001.mp3
```

### 배치 파일 (Windows 간편 실행)

| 파일 | 기능 |
|------|------|
| `hsk.bat` | 메뉴 기반 실행기 (분석/결과보기 통합) |
| `open_listening.bat` | 듣기 분석 결과 HTML 바로 열기 |
| `open_vocabulary.bat` | 단어 분석 결과 HTML 바로 열기 |
| `create_shortcut.vbs` | 바탕화면 바로가기 생성 스크립트 |

### 바탕화면 바로가기 생성

`create_shortcut.vbs`를 더블클릭하면 바탕화면에 바로가기가 생성됩니다.

## 프로젝트 구조

```
hsk_analyzer/
├── .env                  # OpenAI API 키 (git 제외)
├── .env.example          # API 키 템플릿
├── .gitignore            # git 제외 파일 목록
├── requirements.txt      # Python 패키지 목록
├── README.md             # 이 문서
│
├── run.py                # 메인 실행 스크립트 (CLI)
├── config.py             # 설정값 (경로, 모델명, 배치 크기 등)
├── models.py             # 데이터 클래스 정의
├── transcriber.py        # Whisper API 음성 인식
├── analyzer.py           # GPT API 문장 분석
├── renderer.py           # Jinja2 HTML 렌더링
├── cache_manager.py      # JSON 파일 기반 캐싱
│
├── hsk.bat               # Windows 메뉴 실행기
├── open_listening.bat    # 듣기 HTML 바로 열기
├── open_vocabulary.bat   # 단어 HTML 바로 열기
├── create_shortcut.vbs   # 바탕화면 바로가기 생성
│
├── templates/            # HTML 템플릿
│   ├── base.html         # 기본 레이아웃 + CSS + JS
│   ├── track.html        # 트랙별 분석 페이지
│   ├── combined.html     # 통합 분석 페이지 (사이드바 포함)
│   └── index.html        # 전체 목록 페이지
│
├── output/               # 생성된 HTML (자동 생성, git 제외)
│   ├── listening.html    # 듣기 통합 페이지
│   ├── vocabulary.html   # 단어 통합 페이지
│   └── index.html        # 전체 목록
├── cache/                # API 응답 캐시 (자동 생성, git 제외)
│   ├── transcriptions/   # Whisper 인식 결과
│   └── analyses/         # GPT 분석 결과
└── venv/                 # 가상환경 (git 제외)
```

## 처리 흐름

```
MP3 파일
  │
  ▼
[Whisper API] ─── 음성 인식 ──→ 중국어 텍스트
  │                                  │
  │                          문장 분리 + 마커 제거
  │                                  │
  ▼                                  ▼
[캐시 저장] ◄────────────── [GPT API] ─── 문장별 분석
                                         │
                                    병음 / 단어 / 문법 / 번역
                                         │
                                         ▼
                                  [Jinja2 렌더링]
                                         │
                                         ▼
                              통합 HTML 페이지 (사이드바 + 접이식)
```

## HTML 페이지 기능

- **사이드바 네비게이션**: 트랙 목록 + 검색 기능으로 빠른 이동
- **통합 뷰**: 소스별 전체 트랙을 하나의 페이지에 통합
- **접이식 트랙**: 각 트랙을 클릭해서 펼치기/접기
- **오디오 플레이어**: 트랙별 배속 조절 (0.5x ~ 1.25x), 5초 되감기/앞으로
- **루비 주석**: 한자 위에 병음 자동 표시
- **품사별 색상**: 동사(빨강), 명사(파랑), 형용사(주황) 등 색상 구분
- **문법 해설**: 접이식(클릭하면 펼침) 문법 설명 + 예문
- **다크/라이트 모드**: 우측 상단 버튼으로 전환
- **반응형 디자인**: 모니터 크기에 맞춰 동적 레이아웃
- **진행률 바**: 전체 분석 진행 상황 표시
- **맨 위로 가기**: 스크롤 시 플로팅 버튼 표시

## 설정 변경

`config.py`에서 주요 설정을 변경할 수 있습니다:

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `GPT_MODEL` | `gpt-5-mini` | GPT 모델 (gpt-4o-mini, gpt-4.1-nano 등) |
| `WHISPER_MODEL` | `whisper-1` | Whisper 모델 |
| `ANALYSIS_BATCH_SIZE` | `5` | GPT 한 번 호출에 보낼 문장 수 |
| `API_DELAY_SECONDS` | `0.5` | API 호출 간 대기 시간 |
| `MAX_FILE_SIZE_MB` | `25` | Whisper API 파일 크기 제한 |
| `MP3_SOURCES` | (경로 dict) | MP3 소스 디렉토리 경로 |

## MP3 소스

| 소스 | 키 | 파일 수 | 설명 |
|------|------|---------|------|
| 듣기 | `listening` | ~100 트랙 | HSK 5급 듣기 MP3 |
| 단어 | `vocabulary` | ~2500개 | HSK 5급 단어별 MP3 |

## API 비용 참고

| 모델 | 입력 (100만 토큰) | 출력 (100만 토큰) |
|------|-------------------|-------------------|
| gpt-5-mini | $0.25 | $2.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-5-nano | $0.05 | $0.40 |
| Whisper | $0.006/분 | - |

듣기 트랙 전체(~100개) 분석 시 약 $7~15 정도 소요됩니다 (모델에 따라 상이).

## 기술 스택

- **Python 3.10+**
- **OpenAI API** - Whisper (음성 인식) + GPT (문장 분석)
- **Jinja2** - HTML 템플릿 렌더링
- **pypinyin** - 병음 변환 (폴백용)
- **jieba** - 중국어 단어 분리 (폴백용)
- **pydub** - 대용량 MP3 파일 분할 (ffmpeg 필요)

## 라이선스

MIT License
