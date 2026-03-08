# HSK 중국어 듣기 분석기

HSK 5급 듣기 시험 MP3를 음성인식하고, 문장별 상세 분석(병음/단어/문법/번역)을 생성하여 학습용 HTML로 렌더링하는 도구입니다.

## 주요 기능

- **음성인식 (FunASR)**: Paraformer-zh 로컬 모델로 MP3 → 텍스트 변환 (무료, CPU 실행)
- **문제별 오디오 분할**: FunASR 타임스탬프 기반으로 복수문제 트랙을 개별 MP3로 분할
- **3인1조 에이전트 분석**: Claude Agent 3개가 독립 분석 → 교차 검증 → 병합 (GPT 대비 품질 대폭 향상)
- **통합 HTML 페이지**: 사이드바 네비게이션, 검색, 오디오 플레이어, 다크모드
- **캐싱**: 음성인식/분석 결과를 JSON으로 캐시하여 재처리 불필요

## 아키텍처

```
MP3 음원
  │
  ▼
[FunASR Paraformer-zh] ── 음성인식 ──→ 텍스트 + 문자별 타임스탬프
  │
  ├─→ [문제 병합] ── 공통 지문 문제 그룹 감지/병합
  │
  ├─→ [오디오 분할] ── 타임스탬프 기반 문제별 MP3 분리
  │     └─→ [정밀 트리밍] ── 2차 FunASR로 잔여분 제거
  │           └─→ [품질 검증] ── 175/175 OK (100%)
  │
  ├─→ [Agent 팀 분석] ── 3개 에이전트 병렬 분석 + 교차 검증
  │     └─→ 병음/단어(全형태소)/문법/번역/학습팁
  │
  └─→ [HTML 렌더링] ── Jinja2 통합 페이지 생성
```

## 파이프라인 모듈

| 단계 | 모듈 | 설명 |
|------|------|------|
| 음성인식 | `transcriber.py` | FunASR Paraformer-zh + VAD + 구두점 복원 |
| 문제 병합 | `merge_shared_questions.py` | '第X到Y题' 패턴 감지, 공통 지문 문제 그룹 병합 |
| 오디오 분할 | `split_audio_by_questions.py` | questions 배열 + 타임스탬프 기반 정밀 분할 |
| 정밀 트리밍 | `precision_trim.py` | 2차 FunASR로 분할 파일 앞/뒤 잔여분 제거 |
| 품질 검증 | `verify_splits.py` | 재인식 후 원본 대비 유사도 검증 (OK/WARN/FAIL) |
| 문장 분석 | `analyzer.py` | 문장별 상세 분석 생성 |
| HTML 출력 | `renderer.py` | 통합/개별 HTML 생성 |
| CLI | `run.py` | 전체 파이프라인 실행 |

## 분석 품질: 3인1조 에이전트 팀

GPT 단일 분석의 품질 한계를 극복하기 위해 **3개 독립 에이전트**가 동일 문장을 분석하고, 결과를 교차 검증하여 병합합니다.

### 분석 데이터 구조

```json
{
  "original": "请您系好安全带。",
  "pinyin_full": "Qǐng nín jì hǎo ānquándài.",
  "words": [
    {
      "word": "系",
      "pinyin": "jì",
      "part_of_speech": "동사",
      "meaning_ko": "매다, 묶다",
      "meaning_detail": "多音字: jì=매다(系鞋带), xì=계통(关系). 안전벨트 맥락에서는 반드시 jì."
    }
  ],
  "grammar_points": [{"pattern": "请+V", "explanation_ko": "정중한 요청", "example": "请坐。"}],
  "translation_ko": "안전벨트를 매 주세요.",
  "translation_literal_ko": "청하다 당신 매다 잘 안전띠.",
  "difficulty_note": "多音字 '系'는 HSK 시험 빈출.",
  "role": "화자A"
}
```

### GPT 대비 개선점

| 항목 | GPT (기존) | Agent 팀 (현재) |
|------|-----------|----------------|
| 多音字 | 미표기 | 전수 표기 + 용례 |
| meaning_detail | 1문장, 피상적 | 2~3문장, 콜로케이션/시험팁 |
| 문법 포인트 | 1~2개 | 3~5개, HSK 급수별 |
| 누락 형태소 | 자주 발생 | 전수 포함 |
| 한국어 자연스러움 | 번역체 | 자연스러운 한국어 |

## 오디오 분할 파이프라인

18개 복수문제 트랙을 175개 개별 MP3로 분할하는 과정:

1. **문제 병합**: 공통 지문 문제(예: Q31~Q33) 감지 후 하나의 question으로 병합
2. **타임스탬프 분할**: FunASR 문자별 타임스탬프로 각 문제의 시작/끝 지점 결정
3. **패딩**: 앞 500ms (문제 번호 마커), 뒤 800ms (여운), 겹침 방지 200ms
4. **정밀 트리밍**: 분할 파일에 FunASR 재실행 → 원본 텍스트와 비교 → 잔여분 제거
5. **검증**: 전체 175개 파일 OK (유사도 85% 이상)

### 해결한 기술적 문제

| 문제 | 원인 | 해결 |
|------|------|------|
| 타임스탬프 불일치 | ct-punc 구두점 복원 시 문자 수 변경 | 구두점 제거 후 raw 문자 인덱스 매핑 |
| 마커 미감지 | FunASR이 중국어 숫자 마커(一,二,三) 미인식 | questions 배열 기반 분할로 전환 |
| 인접 문제 잔여음 | 분할점 부정확 | 2차 FunASR 정밀 트리밍 |
| 공통 지문 분할 오류 | 같은 지문의 문제들이 개별 분할 | 사전 병합 후 분할 |

## 사용법

```bash
# 전체 파이프라인
python run.py

# 특정 소스/트랙
python run.py --source listening
python run.py --track TRACK001

# 오디오 분할
python split_audio_by_questions.py           # 전체
python split_audio_by_questions.py TRACK010  # 특정 트랙

# 정밀 트리밍
python precision_trim.py TRACK135

# 분할 검증
python verify_splits.py
```

## 설치

```bash
git clone https://github.com/CuteRyan/hsk-analyzer.git
cd hsk-analyzer
python -m venv venv
./venv/Scripts/pip install openai jinja2 pypinyin jieba pydub funasr
```

시스템 요구사항: Python 3.10+, ffmpeg

## 프로젝트 구조

```
hsk_analyzer/
├── run.py                        # CLI 진입점
├── config.py                     # 경로/모델 설정
├── transcriber.py                # FunASR 음성인식
├── analyzer.py                   # 문장 분석
├── renderer.py                   # HTML 렌더링
├── models.py                     # 데이터 모델
├── split_audio_by_questions.py   # 문제별 오디오 분할
├── merge_shared_questions.py     # 공통 지문 문제 병합
├── precision_trim.py             # 2차 정밀 트리밍
├── verify_splits.py              # 분할 품질 검증
├── templates/                    # Jinja2 HTML 템플릿
├── cache/                        # (gitignore) 캐시 데이터
└── output/                       # (gitignore) 생성된 HTML/MP3
```

## 라이선스

MIT License
