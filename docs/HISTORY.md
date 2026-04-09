# HSK 분석기 개발 히스토리

## 2026-04-09: 하네스 엔지니어링 재설계

### 1. 메모리 3계층 아키텍처 구축
- `HSK/CLAUDE.md` + `hsk_analyzer/CLAUDE.md` 생성 (프로젝트/모듈별 규칙)
- `.claude/rules/` 3개 생성 (cache-management, testing, html-rendering)
- MEMORY.md 리팩토링: 90줄 내용 → 18줄 순수 인덱스 + 7개 topic 파일

### 2. 코드 품질 자동화
- **pyproject.toml**: ruff, mypy, pytest 통합 설정
- **ruff**: 린트 + 포맷 자동화, 기존 코드 98건 자동 수정
- **pre-commit hooks**: 커밋 시 자동 lint/format 검사
- **.vscode/settings.json**: format-on-save, pytest 활성화
- **GitHub Actions CI**: push 시 lint → format → mypy → pytest 자동 실행

### 3. 테스트 인프라 (103개 테스트)
- `test_models.py`: to_dict/from_dict 라운드트립 (150문장 스케일)
- `test_cache_manager.py`: tmp_path 격리, 120트랙 스케일
- `test_renderer_utils.py`: _chinese_to_int 1~99 전수, _build_ruby_html
- `test_analyzer_parsing.py`: _split_sentences 문장 분리 로직
- `test_validator.py`: 품사 정규화, 역할 검증, 커버리지 계산

### 4. GPT 출력 검증 가드레일 (validator.py)
- **문제**: GPT 품사 표기가 트랙마다 불일치 (중국어/한국어 혼용, 비표준 변종 29+종)
- **해결**: `validator.py` — 매핑 테이블 기반 자동 교정
  - `normalize_part_of_speech()`: 중국어→한국어, 비표준→표준, 복합→첫번째
  - `validate_role()`: 역할 오타 교정
  - `check_word_coverage()`: 단어 누락 경고
- **analyzer.py 연동**: `_analyze_batch()` 후 `validate_batch()` 자동 호출
- **기존 캐시 일괄 교정**: `fix_cache_pos.py`로 339개 파일 3,386건 교정
- **결과**: 8,429개 단어 전체 100% 표준 품사 일관성 달성

### 변경/생성 파일
- 신규: pyproject.toml, requirements-dev.txt, .pre-commit-config.yaml
- 신규: validator.py, fix_cache_pos.py
- 신규: .vscode/settings.json, .github/workflows/ci.yml
- 신규: tests/ (5개 테스트 파일 + conftest.py + fixtures)
- 신규: HSK/CLAUDE.md, hsk_analyzer/CLAUDE.md, .claude/rules/ 3개
- 수정: analyzer.py (validator 연동), .gitignore (dev 캐시 추가)
- 수정: 기존 .py 전체 (ruff 자동 포맷/린트 수정)

---

## 2026-03-10: 렌더러 ruby 렌더링 방식 변경 + 템플릿 통합

### 문제 발견
- TRACK029 화자B의 중국어 텍스트가 HTML에서 누락됨
- `"这有什么呀？这样的事，我见多了。"` → `"这有什么呀见多了"` (？这样的事，我 사라짐)
- 병음(pinyin_full)은 정상이었으나 한자만 빠짐

### 원인 분석
- **근본 원인**: 렌더러가 `s.original` (완전한 원문)을 사용하지 않고, GPT가 분석한 `s.words[]` 배열만 루프 돌려서 한자를 조립
- GPT가 words 배열에서 단어를 누락하면 해당 한자가 HTML에서 통째로 사라지는 구조
- 전체 135개 트랙 검사 결과 **939건**의 단어 누락 확인 (GPT 분석 한계)
- JSON(transcription, analysis)에는 원문이 제대로 있었으나 렌더러가 이를 활용하지 않았음

### 해결 방법
1. **`renderer.py`에 `_build_ruby_html()` 함수 추가**
   - original 텍스트를 기준으로 words를 순서대로 `find()` 매칭
   - 매칭된 단어 → `<ruby>한자<rt>병음</rt></ruby>` 태그
   - 매칭 안 되는 글자 (GPT 누락분, 구두점 등) → ruby 없이 그대로 출력
   - GPT가 문법 패턴(`连...都...` 등)을 word에 넣은 경우 → skip (90건)

2. **템플릿 통합**
   - 기존: `track.html`(개별)과 `sentence_card.html`(통합)에 문장 카드 코드가 중복
   - 변경: `track.html`에서 중복 코드(65줄) 삭제, `{% include "sentence_card.html" %}` 사용
   - 이제 문장 카드 수정 시 `sentence_card.html` 한 곳만 고치면 됨

### 변경 전후 비교
```
변경 전 (words만 루프):
  {% for w in s.words %}
    <ruby>{{ w.word }}<rt>{{ w.pinyin }}</rt></ruby>
  {% endfor %}

변경 후 (original 기준 매칭):
  {{ build_ruby(s.original, s.words) }}
```

### 검증 결과
- 전체 135개 트랙: OK 135, FAIL 0
- 장문 트랙 (TRACK135 191문장 포함) 전부 원문 그대로 렌더링 확인
- listening.html + 개별 HTML 135개 + 분할 HTML 204개 재생성 완료

### 변경 파일
- `renderer.py`: `_build_ruby_html()` 추가, Jinja2 globals에 `build_ruby` 등록
- `templates/sentence_card.html`: words 루프 → `build_ruby()` 호출
- `templates/track.html`: 중복 문장 카드 코드 삭제, include로 통합

---

## 2026-03-08: 전체 캐시 교정 작업

- transcription 문장분리/역할태깅 + analysis 재생성 + 렌더러 개선
- 상세: 메모리 `cache_fix_2026-03-08.md` 참조

## 이전 작업 (요약)

- FunASR Paraformer-zh 전환 (Whisper 대체)
- 음원 분할 (split + precision_trim + merge), 175개 전체 검증 통과
- 통합/개별 HTML 렌더링, 문제별 그룹화
