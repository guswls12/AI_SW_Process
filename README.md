# SW 배포 파이프라인 도구

차량용 임베디드 SW 변경점에 대해 Claude API 로 자동 리뷰를 수행하는 PyQt6 데스크탑 앱.

- **변경점 요약** — 파일/함수별 수정 내용을 표로 정리
- **취약점 분석** — cat1~cat6 SW 품질 결함 + CERT-C / MISRA-C 정적 분석 위반
- **Codebeamer 연동** — 과거 이슈 데이터와 변경점 대조 (선택) + AI 리뷰 결과를 트래커에 업로드
- **사용자 지정 응답 토큰** — 분석 시작 다이얼로그 슬라이더로 4K~64K 조절 (한도 잘림 시 ⚠ 경고)
- **결과물 저장** — Markdown / HTML / DOCX 다중 포맷
- **DIFF 내보내기** — 코드 변경점을 Excel / HTML 로 추출 (대용량 파일 대응 최적화)

---

## 빠른 시작 (개발 모드)

### 1. Python 환경

Python 3.11 이상 권장.

```bash
# 가상환경 생성 (권장)
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS/Linux

# 의존성 설치
pip install -r requirements.txt
```

### 2. Anthropic API 키 설정

```bash
# Windows (영구 설정)
setx ANTHROPIC_API_KEY "sk-ant-..."

# Windows (현재 셸만)
set ANTHROPIC_API_KEY=sk-ant-...

# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."
```

키가 없으면 AI 분석 단계에서 401 오류가 발생합니다. (앱은 켜지지만 분석 실행 시 실패)

### 3. 실행

**반드시 프로젝트 루트에서 실행해야 합니다** (상대 경로 `prompts/*.md` 가 CWD 기준):

```bash
python main.py
```

---

## 프로젝트 구조

```
project/
├── main.py                ← MainWindow, 위젯 레이아웃 + 시그널을 컨트롤러에 와이어링 (엔트리포인트)
├── config.py              ← 색상 토큰, QSS, 헬퍼 함수
│
├── controllers/           ← 흐름 제어를 영역별로 분리
│   ├── cb_controller.py   ← Codebeamer 컨텍스트 + 다이얼로그 (CbController)
│   ├── diff_controller.py ← DIFF 워커 라이프사이클 (DiffController)
│   └── ai_controller.py   ← Claude API 흐름 + 결과 라우팅 (AiController)
│
├── core/                  ← Qt 의존없는 도메인 로직
│   ├── model.py           ← diff 비교, 함수 범위 탐지
│   └── worker.py          ← 프롬프트 상수 + OPTION_MD_FILES 매핑
│
├── workers/               ← Qt QThread 백그라운드 작업자
│   ├── diff_worker.py       ← 폴더 DIFF 추출 (Claude API 무관)
│   ├── prompts_worker.py    ← Claude API 호출 워커 (ReviewWorker)
│   └── cb_upload_worker.py  ← Codebeamer 업로드 워커 (CbUploadWorker)
│
├── integrations/          ← 외부 시스템 연동
│   └── codebeamer/        ← Codebeamer 패키지 (단일 파일을 8개로 분할)
│       ├── __init__.py        ← 공개 API 재수출 (외부 import 경로 호환)
│       ├── config.py          ← 경로/상수, load_config, save_config, parse_*  (Qt 무관)
│       ├── text.py            ← _clean_text — HTML/위키마크업 정제 (Qt 무관)
│       ├── api.py             ← CbFetcher — REST API 클라이언트 (Qt 무관)
│       ├── ui_primitives.py   ← _ca / _ClickableWidget / _ElidedLabel / _FetchWorker
│       ├── dialogs.py         ← CbConfigDialog + _FetchSelectDialog
│       └── section_widget.py  ← CbSectionWidget — 4분할 탭 개별 섹션
│
├── view/                  ← UI 패키지
│   ├── ui_md.py           ← 마크다운 → HTML 변환
│   ├── ui_save.py         ← AI 분석 결과 저장 (MD/HTML/DOCX)
│   ├── ui_diff_export.py  ← 코드 변경점(DIFF) Excel/HTML 내보내기 (write_only + 병렬)
│   ├── ui_cb_upload.py    ← Codebeamer 업로드 다이얼로그
│   ├── ui_input.py        ← 좌측 InputPanel
│   ├── ui_result.py       ← 우측 ResultPanel + 보조 위젯
│   └── ui_dialog.py       ← DiffLoadingDialog
│
├── prompts/               ← 외부화된 프롬프트 MD
│   ├── CERT_C_Rules_Summary.md     ← 옵션별 규칙 본문
│   ├── MISRA_C_*.md
│   └── system/                     ← 시스템 프롬프트 (코드에서 _load() 로 읽음)
│
├── assets/                ← 정적 리소스
└── docs/                  ← 문서 (버전관리.txt, color_reference.html)
```

자세한 모듈 의존성 흐름은 [CLAUDE.md](CLAUDE.md) 참조.

---

## EXE 빌드 (배포용)

```bash
pip install pyinstaller
pyinstaller CodeReviewer.spec
```

산출물: `dist/CodeReviewer.exe` (단일 파일, 약 64MB).

빌드 시 `prompts/` 폴더가 함께 번들됩니다 (`CodeReviewer.spec` 의 `datas` 항목 참조).

---

## 설정 파일

### `cb_config.json` — Codebeamer 자격증명

앱에서 Codebeamer 연결 테스트를 하면 자동으로 생성/갱신됩니다. **자격증명이 평문으로 저장되므로 절대 git 에 커밋하지 마세요** (`.gitignore` 에 등록됨).

```json
{
  "url": "https://codebeamer.example.com/cb",
  "username": "...",
  "password": "...",
  "tracker_ilcu": "...",
  ...
  "last_upload_tracker_id": "9486521",     // 직전 업로드 대상 트래커
  "last_upload_item_id": "",                // 코멘트 모드 직전 이슈
  "last_upload_mode": "new_issue",          // 'new_issue' | 'comment'
  "last_upload_attach_md": true,
  "last_upload_attach_html": true,
  "last_upload_parent_id": ""               // 새 이슈 생성 시 상위 이슈 ID (하위로 매달 때)
}
```

EXE 실행 시 위치: `%APPDATA%\CodeReviewer\cb_config.json`
개발 모드: 프로젝트 루트의 `cb_config.json`

`last_upload_*` 필드들은 "📤 CB 업로드" 다이얼로그가 직전 사용값을 자동으로 채우기 위해 보관합니다 (수동 편집 불필요).

### `prompts/system/*.md` — 시스템 프롬프트

비개발자도 메모장으로 직접 편집 가능. `{cats}`, `{standards}` 같은 중괄호 플레이스홀더는 코드가 `.format(...)` 로 치환하니 건드리지 마세요.

---

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `FileNotFoundError: prompts/...` | `python main.py` 를 프로젝트 루트가 아닌 곳에서 실행함 |
| `❌ ANTHROPIC_API_KEY 환경변수를 확인해주세요` | API 키 미설정 또는 셸 재시작 필요 |
| Codebeamer 연결 401 | URL / ID / PW 확인. SSO 사용 환경이면 CB 의 `personal access token` 사용 권장 |
| `ModuleNotFoundError: PyQt6` | 가상환경 미활성 또는 `pip install -r requirements.txt` 누락 |
| 빌드 후 EXE 실행 시 `prompts` 누락 | `CodeReviewer.spec` 의 `datas=[('prompts', 'prompts'), ...]` 확인 |
| EXE 에서 `ModuleNotFoundError: integrations.codebeamer.xxx` | `codebeamer` 가 패키지로 바뀐 후 PyInstaller 가 일부 서브모듈을 못 찾는 경우. spec 의 `hiddenimports` 에 `'integrations.codebeamer.config'`, `'integrations.codebeamer.api'`, `'integrations.codebeamer.section_widget'` 등 추가 |

---

## 변경 이력

[docs/버전관리.txt](docs/버전관리.txt) 참조.

### 최근 변경 (2026-05)

- **AI 리뷰 결과 → CB 트리상의 "하위 이슈" 로 생성** (`integrations/codebeamer/api.py`) —
  CB 업로드 다이얼로그의 "상위 이슈 ID" 필드에 부모 이슈 번호를 넣으면, 새 이슈가 그
  부모의 **하위(child) 로 트리에 매달리도록** 처리.
  - 기존 동작: `POST /api/v3/trackers/{tid}/items` 로 일단 생성 → 그 후 `set_parent`
    로 PATCH/PUT 시도 → 이 CB 인스턴스가 PATCH/PUT 미지원이라 모든 시도 실패 →
    "상위 ─" 빈 칸 + 본문 텍스트 링크만 남는 폴백.
  - 신규 동작: **CB 웹 UI 가 사용하는 `?parent_id=` 쿼리 파라미터 패턴** 을
    `create_item` 단계에서 우선 적용 (실제 웹 UI URL: `/cb/tracker/{tid}/create?parent_id={pid}`).
    6가지 변형 (`?parent_id=` / `?parentItemId=` / `?parentId=` 쿼리 + payload 의
    `parent:{id:X}` / `parentItemId:X` / `parent:X`) 을 순차 시도 → 첫 성공에서 멈춤
    (중복 이슈 방지) → `_check_parent_set` 으로 fetch_item_detail 검증 → 실패 시에만
    기존 `set_parent` 폴백 → 최종 실패해도 이슈는 만들어지고 본문 상단 링크로 추적 가능.
  - 모든 단계가 stderr 에 로깅됨 (`[CREATE-ITEM 1/6] POST .../items?parent_id=991130 ...`
    → `✓ 생성됨` → `✓ 상위 #991130 생성 시점 연결 확인됨`).
  - `cb_config.json` 에 `last_upload_parent_id` 필드 추가 — 직전 부모 ID 자동 복원.

- **`integrations/codebeamer.py` (4,113줄) 패키지로 분할** — 단일 파일이
  너무 비대해져 가독성·탐색성이 떨어졌던 문제 해결. `integrations/codebeamer/`
  디렉토리로 변경하고 책임별 7개 파일로 쪼갬: `config.py` (경로·설정), `text.py`
  (HTML/위키 정제), `api.py` (CbFetcher REST 클라이언트), `ui_primitives.py`
  (_ca/_ClickableWidget/_ElidedLabel/_FetchWorker), `dialogs.py`
  (CbConfigDialog/_FetchSelectDialog), `section_widget.py` (CbSectionWidget).
  `__init__.py` 가 공개 심볼 (CbFetcher, CbConfigDialog, CbSectionWidget,
  load_config, save_config, load_cb_context, parse_tracker_id_from_url,
  parse_item_id_from_url, _BASE) 을 모두 재수출하므로 외부의
  `from integrations.codebeamer import ...` 경로는 **그대로 작동** — 호출자 5곳
  (cb_controller / ai_controller / ui_input / ui_cb_upload / ui_result)
  한 줄도 수정 안 함.
  - 분할 전: 4,113줄 1개 파일
  - 분할 후: 평균 ~530줄 8개 파일 (`config` 139줄 / `api` 515줄 / `dialogs` 390줄
    / `section_widget` 2,822줄 등)
  - `_get_data_dir()` 의 `os.path.dirname` 횟수를 2 → 3 으로 조정 — 파일 깊이가
    `integrations/codebeamer.py` 에서 `integrations/codebeamer/config.py` 로 한 단계
    깊어졌기 때문. `cb_config.json` 위치는 프로젝트 루트로 그대로 유지됨.
  - `CbSectionWidget` (2,822줄) 은 1차 분할에서 그대로 둔 가장 큰 덩어리. 추후 별도
    리팩터링 시 view-mode (accordion / checklist / chip) 별로 더 잘게 쪼갤 여지 있음.

- **AI 리뷰 결과 → Codebeamer 업로드** — 우측 결과 패널 상단에 **"📤 CB 업로드"** 버튼
  추가. 클릭 시 다이얼로그가 떠서 ① 트래커 URL/ID (직전 사용값 자동 채움), ② 새 이슈
  생성 / 기존 이슈에 코멘트 추가 라디오, ③ MD/HTML 첨부 여부를 받음. 업로드는
  `workers/cb_upload_worker.py` 의 `CbUploadWorker` (QThread) 가 백그라운드에서 처리하므로
  UI 가 멈추지 않고, 진행상태는 상태바에 표시. 완료 시 안내 다이얼로그에서 "브라우저에서
  열기" 클릭하면 새 이슈 페이지가 곧바로 열림.
  - 이슈 제목: `[프로젝트명] SW 배포 파이프라인 - YYYY-MM-DD HH:MM`
  - 본문: 변경점 요약 + `---` + 취약점 분석 markdown (CB 가 거부 시 `descriptionFormat`
    제거 후 재시도 폴백)
  - 첨부: 동일 내용을 `.md` / `.html` 단독 문서로 추가 — HTML 은 `view/ui_md.py` 의
    변환기로 헤더/표/코드블록 렌더링 적용
  - 직전 사용값(트래커 ID, 모드, 첨부 여부) 은 `cb_config.json` 의 `last_upload_*` 필드로
    저장 → 다음번 업로드 시 자동 복원
  - CB 측 신규 메서드: `CbFetcher.create_item` / `add_comment` / `add_attachment`
    (`integrations/codebeamer.py`). 모두 v3 API 우선, 일부 응답 거부 시 legacy `/rest/`
    엔드포인트로 폴백.

- **DIFF Excel/HTML 내보내기 성능 최적화** (`view/ui_diff_export.py`) — 대용량 파일
  추출 시간을 대폭 단축 (출력 형식·내용은 그대로).
  - **openpyxl `write_only` + `NamedStyle`** — 셀 단위 `Font/PatternFill/Alignment`
    개별 할당 → `WriteOnlyCell` + 사전 등록된 11개 NamedStyle 을 row 단위로 스트리밍
    저장. 1만 줄 이상 파일에서 보통 5~15배 단축.
  - **폴더 모드 다중 파일 병렬 저장** — `ThreadPoolExecutor(max_workers=min(8, cpu))` 로
    체크된 파일들을 동시에 처리. 출력 경로는 메인 스레드에서 미리 계산해 파일명 충돌
    방지.
  - **`QProgressDialog`** — 진행률 (`N/M`) 표시 + 취소 버튼. 메인 루프에서
    `QApplication.processEvents()` 호출로 UI 무응답 방지.

- **사용자 지정 max_tokens 슬라이더** — `controllers/ai_controller.py` 의 분석 시작 확인
  다이얼로그에 슬라이더 추가 (4,000 ~ 64,000 토큰, 1K 단위). 변경점 요약 / 취약점 분석
  양쪽 호출에 동일 적용. 세션 내 마지막 선택값은 다음 호출 시 기본값으로 복원.

- **응답 잘림 자동 감지** — `workers/prompts_worker.py` 의 `ReviewWorker` 가
  스트림 종료 후 `stop_reason == "max_tokens"` 를 확인. 잘렸을 경우 결과 텍스트
  맨 위에 `> ⚠️ 응답이 토큰 한도에서 잘렸습니다 ...` blockquote 를 끼우고,
  시그널을 `(text, was_truncated: bool)` 시그니처로 emit 해 컨트롤러가 상태바에
  ⚠ 경고를 표시.

- **잘림 시 이어서 분석 (continuation prompt)** — `ContinueVulnWorker` 신규.
  취약점 분석이 토큰 한도에서 잘리면 자동으로 팝업이 떠서 사용자가 새 토큰 한도를
  지정할 수 있음. 수락 시 `messages = [user(body), assistant(partial), user("이어서 작성하세요")]`
  3-turn 구조로 호출 — Claude Sonnet 4.6 은 assistant 로 끝나는 대화를 거부
  ("This model does not support assistant message prefill") 하므로 user 지시
  메시지로 마무리. 모델이 이전 assistant 출력을 컨텍스트로 보고 이어 작성하므로
  **이전까지 분석된 내용은 그대로 유지되고 추가분만 새로 토큰 소비**. 이어서
  분석한 결과가 또 잘리면 동일한 팝업이 다시 떠서 chained continuation 가능.


- **DOCX 저장 정식 렌더링** (`view/ui_save.py`)
  - 기존: 마크다운 본문을 한 줄씩 plain paragraph 로 덤프 → `####` / `|...|` 가
    원본 텍스트로 노출 (가독성 ↓)
  - 신규: `_md_to_docx` 마크다운 파서 추가 — 헤더는 Heading 1~4, 표는 실제 Word
    표 (Light Grid Accent 1 / Table Grid 폴백, 헤더 행 bold + 옅은 파랑 배경),
    코드블록은 모노스페이스 + 음영 단락, 인라인 `**bold**` / `` `code` `` /
    `*italic*` 모두 run 단위로 서식 적용
  - `ui_md._md_to_html` 와 동일한 마크다운 규칙 (테이블 셀 줄병합, 언어 힌트별
    코드블록 분기 등) 을 그대로 포팅 → HTML/DOCX 출력이 일관된 모양

- **마크다운 렌더링 가독성 개선** (`view/ui_md.py`)
  - 언어 힌트 없는 코드펜스 ` ``` ` → 라이트 슬레이트 콜아웃 (발생 시나리오용,
    `#F1F5F9` 배경 + 좌측 보더). ` ```c ` 등 언어 힌트 있는 블록은 기존 다크
    코드 블록 유지.
  - 표 셀 안의 인라인 `<code>` 톤다운 — 노란 펠릿 (`#FDE68A`) → 옅은 슬레이트
    배지 (`#F1F5F9` + 1px 보더), SA 표 같은 빽빽한 셀의 시각 노이즈 감소.
  - 표 셀 `word-break: keep-all` 로 한글 어절 단위 줄바꿈 (이전 `break-word` 는
    글자 단위로 깨졌음).
  - `[CERT-C]` / `[MISRA-C:YYYY]` 표준 태그 앞 자동 줄바꿈 — SA 표의 다중 규칙
    셀에서 한 규칙씩 줄을 차지하도록.

- **`prompts/system/rule_violation_section.md` 보강** — 규칙 ID 백틱 래핑·표준 태그
  형식·슬래시 금지 규칙 추가. AI 가 SA 표를 일관된 포맷 (`[MISRA-C:2012]` `` `Rule 9.1` ``)
  으로 생성하도록 함.

---

## AI 어시스턴트용 가이드

Claude Code 등 AI 도구로 이 프로젝트를 다룰 때 참고할 모듈 의존성 / 코드 컨벤션은 [CLAUDE.md](CLAUDE.md) 에 정리돼 있습니다.
