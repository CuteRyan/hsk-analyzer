# HSK 분석기 변경 이력

## 2026-03-08: 3인1조 에이전트 팀 분석 도입 + 오디오 정밀 분할

### 분석 엔진 교체: GPT → Claude Agent 팀 (3인1조)

#### 변경 사유
- GPT(`gpt-5-mini`) 분석 품질 부족: 피상적 meaning_detail, 多音字 미표기, 문법 설명 빈약
- Claude Agent 팀 방식: 3개 독립 에이전트가 동일 문장을 병렬 분석 → 교차 검증 → 병합
- 결과 품질 대폭 향상: 多音字 전수 표기, 어원·콜로케이션·시험 팁, 한국어 학습자 맞춤 설명

#### 분석 방법론
1. 5트랙 단위 배치 구성 (문장 15~45개)
2. Agent A, B, C가 동일 문장을 독립적으로 분석
3. 3개 결과를 교차 검증하여 최고 품질 결과 병합
4. `cache/analyses/TRACKXXX.json` 형식으로 저장

#### 분석 데이터 구조 (문장별)
```json
{
  "original": "원문",
  "pinyin_full": "성조 부호 병음 (ā á ǎ à)",
  "words": [{
    "word": "단어",
    "pinyin": "병음",
    "part_of_speech": "품사(한국어)",
    "meaning_ko": "뜻",
    "meaning_detail": "상세 설명 (2문장 이상, 多音字/콜로케이션/시험 팁)"
  }],
  "grammar_points": [{"pattern": "...", "explanation_ko": "...", "example": "..."}],
  "translation_ko": "자연스러운 한국어 번역",
  "translation_literal_ko": "직역",
  "difficulty_note": "학습 팁",
  "role": "화자A/화자B/질문"
}
```

#### 진행 현황
- TRACK001-016: 완료 (16/135 트랙)
- 파이프라인 방식으로 저장과 분석을 동시 병렬 처리

---

### 오디오 문제별 분할 파이프라인

#### 배경
- HSK 듣기 MP3 중 18개 트랙이 복수 문제 포함 (예: TRACK010에 10문제)
- 문제별 개별 재생을 위해 정밀 분할 필요

#### 새 파일들

##### `split_audio_by_questions.py` — FunASR 타임스탬프 기반 정밀 분할
- transcription JSON의 questions 배열 + FunASR 문자별 타임스탬프 활용
- 각 문제의 첫 문장 시작 ~ 마지막 문장 끝 타임스탬프로 분할점 결정
- padding: 앞 500ms (문제 번호 마커 포함), 뒤 800ms (여운), 겹침 방지 200ms
- 출력: `output/audio_splits/TRACK010-01.mp3` ~ `TRACK010-10.mp3`

##### `merge_shared_questions.py` — 공통 지문 문제 병합
- '第X到Y题是根据下面一段话' 패턴 감지
- 공통 지문을 공유하는 문제 그룹(예: Q31~Q33)을 하나의 question으로 병합
- 중국어 숫자(一~四十五) → 정수 변환 지원

##### `precision_trim.py` — 2차 정밀 트리밍
- 이미 분할된 MP3에 FunASR을 재실행하여 개별 파일 타임스탬프 획득
- 원본 텍스트와 인식 텍스트 비교로 앞/뒤 잔여분 감지 및 트리밍
- 원본 시작 300ms 전, 원본 끝 500ms 후까지 유지

##### `verify_splits.py` — 분할 품질 검증
- 각 분할 파일을 FunASR로 재인식 후 원본과 유사도 비교
- OK (≥85%), WARN (50~85%), FAIL (<50%) 분류
- 최종 결과: **175개 전체 OK** (WARN 0, FAIL 0)

#### 문제 해결 과정

| 문제 | 원인 | 해결 |
|------|------|------|
| ct-punc 모델이 문자 수 변경 | 구두점 복원 시 문자 수 불일치 | 구두점 제거 후 raw 문자 매핑 |
| 일부 트랙 마커 미감지 | FunASR이 중국어 숫자 마커를 인식 못함 | questions 배열 기반으로 전환 |
| TRACK135 WARN 10개 | 인접 문제 오디오 잔여분 | precision_trim.py로 2차 트리밍 |
| 공통 지문 문제 분할 오류 | Q31~Q33이 같은 지문인데 개별 분할 | merge_shared_questions.py로 사전 병합 |

#### 분할 결과
- 입력: 18개 복수문제 트랙 (TRACK010~TRACK135)
- 출력: 175개 개별 MP3 파일
- 검증: 175/175 OK (100%)

---

## 2026-03-06: 통합 HTML 출력 + 오디오 플레이어

### 변경 사항
- `renderer.py`: 소스별 통합 HTML 생성 (listening.html, vocabulary.html)
- `templates/combined.html`: 사이드바 네비게이션, 검색, 접이식 트랙, 오디오 플레이어
- 개별 HTML도 동시 생성 (TRACK001.html 등)
- `analyzer.py`: timeout(120초) + 3회 재시도 추가

---

## 2026-03-05: ASR 엔진 교체 (Whisper → FunASR Paraformer-zh)

### 변경 사유
- OpenAI Whisper API: 느린 속도, 낮은 중국어 인식률, hallucination(반복 인식), API 비용 발생
- FunASR Paraformer-zh: 중국어 특화 모델(220M params), 로컬 실행(CPU 가능), 무료, 자동 구두점 복원

### 변경된 파일

#### `transcriber.py` — 전면 재작성
- **제거**: OpenAI 클라이언트 의존성, Whisper API 호출, 청크 분할 로직
- **추가**: FunASR AutoModel 파이프라인 (paraformer-zh + fsmn-vad + ct-punc)
- 모델 lazy loading (`_get_model()`) — 첫 호출 시에만 로드
- `batch_size_s=300` 설정으로 긴 오디오 처리

#### `config.py` — 불필요 설정 제거
- **제거**: `ASR_BACKEND`, `WHISPER_MODEL`, `MAX_FILE_SIZE_MB`, `CHUNK_SIZE_MB`

#### `run.py` — 새 Transcriber 연동
- **변경**: `from transcriber import Transcriber` (기존 `create_transcriber` 팩토리 제거)
- **변경**: `Transcriber(cache)` — OpenAI 클라이언트 불필요
- **제거**: `--asr` CLI 옵션, 다중 백엔드 관련 코드

### FunASR 모델 정보
- **paraformer-zh**: 비자기회귀 중국어 ASR (Alibaba DAMO Academy)
- **fsmn-vad**: 음성 구간 감지 (Voice Activity Detection)
- **ct-punc**: 구두점 자동 복원
- 모델 캐시: `~/.cache/modelscope/` (총 ~944MB)
- 문자별 타임스탬프 제공: `[start_ms, end_ms]` — 문제 분할에 활용

---

## 예정 작업

1. **에이전트 팀 분석 완료** — 나머지 119개 트랙 분석 (현재 16/135)
2. **HTML 템플릿 업데이트** — 분할된 문제별 오디오 플레이어 연동
3. **PWA / 안드로이드 앱** — HTML을 PWA로 만들어 모바일에서 앱처럼 사용
