# hsk_analyzer 모듈

## 파이프라인 흐름

```
MP3 → transcriber.py (FunASR Paraformer-zh)
    → analyzer.py (GPT 문장 분석)
    → renderer.py (Jinja2 HTML 생성)
```

## 핵심 모듈

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 진입점, 파이프라인 오케스트레이션 |
| `transcriber.py` | FunASR Paraformer-zh 음성인식 (VAD+구두점복원) |
| `analyzer.py` | GPT API 호출, 문장별 분석 (timeout 120초, 3회 재시도) |
| `renderer.py` | Jinja2 HTML 렌더링, `_build_ruby_html()` |
| `config.py` | 경로, 모델, 배치 크기 설정 |
| `models.py` | 데이터 모델 (TrackAnalysis, SentenceAnalysis 등) |
| `cache_manager.py` | transcription/analysis JSON 캐시 관리 |

## 음원 분할 도구

| 파일 | 역할 |
|------|------|
| `split_audio_by_questions.py` | FunASR 타임스탬프 기반 문제별 분할 |
| `precision_trim.py` | 2차 정밀 트리밍 (개별 재인식 후 초과분 제거) |
| `merge_shared_questions.py` | 공통 지문 문제 세트 병합 |
| `verify_splits.py` | 분할 검증 (SequenceMatcher, 85%+ OK) |

## 템플릿 구조

| 파일 | 역할 |
|------|------|
| `base.html` | 공통 레이아웃 |
| `combined.html` | 소스별 통합 페이지 (사이드바, 검색, 접이식) |
| `track.html` | 개별 트랙 페이지 |
| `sentence_card.html` | 문장 카드 (유일한 정의 — track.html에서 include) |
| `index.html` | 목록 페이지 |

## 코딩 규칙

- transcription JSON의 `questions` 배열이 문제 그룹화의 기준
- 1문제 트랙도 동일하게 그룹화 (일관성)
- 공통 지문 문제는 반드시 세트로 묶기
- GPT 모델 변경은 `config.py`의 `GPT_MODEL`에서
