## 프로젝트 구조

```
project/
├── main.py                ← MainWindow (9탭 사이드바 + 페이지 스택) + InputShim/ResultShim
│                            어댑터 (컨트롤러 호환 인터페이스) — 약 500줄
├── config.py              ← 색상 토큰, QSS, 헬퍼 함수
│
├── controllers/           ← MainWindow 의 흐름 제어 책임을 영역별로 분리
│   ├── __init__.py
│   ├── cb_controller.py   ← Codebeamer 컨텍스트 로드 / 설정 다이얼로그 (CbController)
│   ├── diff_controller.py ← DIFF 워커 라이프사이클 (단일/폴더/요구사항) — DiffController
│   │                        공개 속성: old_lines / new_lines / changed_text (AI/Export 가 읽음)
│   │                        ─ 단일 파일 모드에서 diff_func_analysis 와 find_changed_functions
│   │                          가 SAME 입력(ignore_comments 일관 적용) 받도록 통일
│   │                          → DIFF VIEW 함수 목록과 AI 변경점 요약 함수 목록 일치
│   ├── ai_controller.py   ← Claude API 호출 흐름 + 결과 라우팅 + 확인 다이얼로그 (AiController)
│   │                        ─ 확인 다이얼로그에 max_tokens 슬라이더 (4K~64K, 세션 내 마지막값 유지)
│   │                        ─ 워커 시그널 (str, bool) 수신 — bool=True 면 토큰 한도 잘림 → ⚠ 상태바
│   │                        ─ 잘림 감지 시 _show_truncation_dialog 팝업 → ContinueVulnWorker 로
│   │                          continuation prompt 이어서 분석 (_continuation_context 보존)
│   │                        ─ MD 파일 로드 2단계:
│   │                          ① BASE_CONTEXT_FILES (항상 로드 — sw_quality 카테고리 정의 등)
│   │                          ② OPTION_MD_FILES (체크된 옵션만 — cert_c/misra_c 등)
│   │                        ─ [대화형AI DISABLED] Q&A 비활성화 블록 보관 (~120줄)
│   ├── srs_review_v2_controller.py
│   │                      ← SRS (요구사항) 검토 워크플로우 컨트롤러 (SrsReviewV2Controller)
│   │                        ─ SrsPage 의 cb_historical_tab + checklist_review_tab 와 연동
│   │                        ─ 변경점/과거차 fetch (CbFetcher) + 변경점 N개 병렬 AI 분석
│   │                          (workers.srs_review_v2_worker) + 결과별 CB 업로드
│   │
│   └── (CbController 안의) on_cb_upload  ← AI 결과 → Codebeamer 업로드 흐름
│                            ─ ResultPanel 의 cb_upload_clicked 시그널 슬롯 (main.py 가 와이어링)
│                            ─ CbUploadDialog 띄워 트래커 ID / 모드 / 첨부 옵션 / **상위 이슈 ID**
│                              (parent_item_id) 받음 — 직전 사용값 last_upload_parent_id 자동 채움
│                            ─ CbUploadWorker (QThread) 스핀 → 진행상태 status bar
│                            ─ 완료 시 QMessageBox + "브라우저에서 열기" → webbrowser.open
│                            ─ 직전 사용값 (last_upload_*  +  last_upload_parent_id)
│                              cb_config.json 에 저장 → 다음 호출 시 자동 채움
│
├── core/                  ← Qt 의존없는 도메인 로직
│   ├── __init__.py
│   ├── model.py           ← diff 비교, C 함수 범위 탐지 (정규식 파서 + difflib)
│   │                        ─ parse_c_functions / diff_func_analysis / find_changed_functions
│   │                        ─ build_unified_diff / diff_stats / strip_comments_from_lines
│   ├── text_io.py         ← 파일 텍스트 읽기 헬퍼 (read_text_lines — 인코딩 자동 감지)
│   └── worker.py          ← BASE_CONTEXT_FILES + OPTION_MD_FILES + CAT_PROMPTS + 시스템 프롬프트
│                            ─ BASE_CONTEXT_FILES : **항상** user body 에 주입되는 분석 기준 문서
│                              (sw_quality → prompts/SW_Quality_Categories.md, cat1~cat6 정의)
│                            ─ OPTION_MD_FILES    : 체크박스로 선택된 옵션 표준 문서
│                              (cert_c / misra_c / misra_c23 / req_diff)
│                            ─ CAT_PROMPTS        : cat1~cat6 검사 지시 stub (각 ~4줄) +
│                              cert_c / misra_c / misra_c23 표준 검사 지시
│                              (각 cat stub 은 user body 의 카테고리 기준 섹션을 참조하는 짧은
│                               지시문만 보유 — cert_c / misra_c 와 동일 패턴)
│                            ─ 큰 시스템 프롬프트(_SYS_SUMMARY/_SYS_VULN_TMPL/
│                              _RULE_VIOLATION_SECTION/_CB_ISSUES_SECTION/
│                              _CB_VULN_SECTION)는 prompts/system/*.md 에서 _load() 로 읽음
│
├── workers/               ← Qt QThread 기반 백그라운드 작업자
│   ├── __init__.py
│   ├── diff_worker.py       ← 폴더 DIFF 추출 (스캔 + 분석, 진행률 emit) +
│   │                          ReqDiffWorker (요구사항 텍스트 DIFF)
│   ├── prompts_worker.py    ← Claude API 호출 워커 (ReviewWorker, ContinueVulnWorker)
│   │                          — 프롬프트 본문은 core.worker 에서 import
│   │                          — BASE_KEYS = cat1~cat6 (항상 포함) +
│   │                            EXTRA_KEYS = cert_c/misra_c/misra_c23 (체크된 것만 포함)
│   │                          — _OPTION_LABELS : option_contents 키 → user body 섹션 라벨 매핑
│   │                            (sw_quality → "SW 품질 결함 카테고리 기준",
│   │                             cert_c → "CERT-C 규칙 기준 (...)" 등)
│   │                          — ReviewWorker: max_tokens 파라미터 (요약·분석 양쪽 동일 적용),
│   │                            stop_reason == "max_tokens" 감지 시 결과 상단에 경고 blockquote
│   │                            삽입 + 시그널 (str, bool) 로 잘림 통지,
│   │                            continuation 컨텍스트(last_vuln_system_prompt /
│   │                            last_vuln_user_body / last_vuln_raw_text) 속성 노출
│   │                          — ContinueVulnWorker: 잘린 분석을 continuation prompt 로 이어서 호출.
│   │                            messages = [user(body), assistant(partial), user("이어서 작성")] 3-turn.
│   │                            Sonnet 4.6 은 assistant 로 끝나는 대화 미지원 → user 지시로 마무리.
│   │                            Claude 가 이전 assistant 출력을 컨텍스트로 보고 이어 작성 → 토큰 절약
│   │                          — [대화형AI DISABLED] QaWorker / _SYS_CHAT 비활성화 블록 (~93줄)
│   ├── cb_upload_worker.py  ← CbUploadWorker — AI 결과 → Codebeamer 업로드 (단일 업로드 흐름)
│   │                          — mode = 'new_issue' 면 CbFetcher.create_item, 'comment' 면 add_comment
│   │                          — parent_item_id 가 주어지면 create_item 에 그대로 전달 → 생성 시점
│   │                            에 부모 연결 (api.py 가 6가지 전략 순차 시도)
│   │                          — 본문 최상단에 `> 📎 상위 항목: [#N](.../issue/N)` 마크다운 링크
│   │                            를 prepend (생성 시점 연결이 실패해도 시각적 추적 보장)
│   │                          — attach_md / attach_html 체크 시 임시 파일 생성 + add_attachment 로 업로드
│   │                          — HTML 첨부는 view.ui_md._md_to_html 로 변환 후 self-contained 문서로 저장
│   │                          — 시그널: progress(str) / done(dict {item_id,url,mode}) / error(str)
│   ├── cb_bulk_upload_worker.py
│   │                        ← CbBulkUploadWorker — 사양 변경 페이지의 [📤 전체 등록] 흐름
│   │                          (변경점 묶음 다중 일괄 업로드)
│   └── srs_review_v2_worker.py ← SrsReviewV2Worker — SWE.1 SRS 페이지의 요구사항 검토 백그라운드 작업자
│                              변경점 1건 입력 (CB 변경점 + 공통 체크리스트/검토/회의록 +
│                              과거차 + 옵션 요구사항 DIFF) → 마크다운 5(+1)섹션 인사이트.
│                              컨트롤러가 변경점 N개를 N개 인스턴스로 병렬 실행.
│                              (prompts/system/srs_review.md + prompts/checklists/*.json 사용)
│
├── integrations/          ← 외부 시스템 연동
│   └── codebeamer/        ← Codebeamer 패키지 (단일 파일 4,113줄 → 8 파일로 분할)
│       ├── __init__.py        ← 공개 API 재수출 — 외부 import 경로 호환 보장
│       │                        (CbFetcher, CbConfigDialog, CbSectionWidget,
│       │                         load_config, save_config, load_cb_context, parse_*, _BASE)
│       ├── config.py          ← _BASE / CB_CFG_FILE / CB_MD_FILE / TRACKER_DEFS
│       │                        load_config / save_config / parse_tracker_id_from_url /
│       │                        parse_item_id_from_url / load_cb_context  (Qt 무관)
│       │                        ─ _get_data_dir() 의 dirname() 호출 횟수 3 — 경로
│       │                          깊이가 한 단계 늘어났으므로 (codebeamer/config.py)
│       ├── text.py            ← _clean_text — HTML/CSS/위키마크업 정제 (Qt 무관)
│       ├── api.py             ← CbFetcher — 세션 로그인 + REST API 클라이언트 (Qt 무관)
│       │                        ─ GET: fetch_tracker_items / fetch_item_detail /
│       │                          fetch_item_children / find_tracker_id / generate_md
│       │                        ─ POST (AI 결과 업로드용):
│       │                          create_item(트래커, 제목, 본문, parent_item_id="") /
│       │                          add_comment(이슈, 텍스트) /
│       │                          add_attachment(이슈, 파일경로) — v3 API 거부 시 legacy /rest 폴백
│       │                        ─ create_item: parent_item_id 가 있으면 **생성 시점에**
│       │                          부모와 함께 만들도록 6가지 전략을 우선 시도 —
│       │                          (1) `?parent_id=` query (CB 웹 UI 패턴), (2) `?parentItemId=`,
│       │                          (3) `?parentId=`, (4) payload `{parent:{id:X}}`, (5) `{parentItemId:X}`,
│       │                          (6) `{parent:X}`. 첫 성공에서 멈춤 (중복 이슈 방지) →
│       │                          _check_parent_set 으로 검증 → 실패 시에만 set_parent 폴백.
│       │                          이 CB 인스턴스는 PATCH/PUT 미지원이라 "생성 후 set_parent"
│       │                          경로는 거의 실패 → 생성 시점 연결이 사실상 유일한 방법.
│       │                        ─ _check_parent_set(item_id, expected_parent) — fetch_item_detail
│       │                          로 가져온 detail 의 parent / subjects / ancestors 중 하나라도
│       │                          기대값과 일치하면 True. set_parent 의 _verify_parent_set 클로저와
│       │                          동일 로직을 메서드로 노출 (재사용).
│       │                        ─ set_parent: 기존 이슈에 parent 설정 — JSON POST 7가지 +
│       │                          legacy 폼 3가지 변형 시도, 매번 fetch_item_detail 검증.
│       │                          create_item 의 폴백 경로로만 호출됨 (직접 호출은 거의 없음).
│       ├── ui_primitives.py   ← _ca (rgba helper) / _ClickableWidget /
│       │                        _ElidedLabel / _FetchWorker (트래커 일괄 조회 QThread)
│       ├── dialogs.py         ← CbConfigDialog (URL/계정/PW 설정) +
│       │                        _FetchSelectDialog (CB 불러오기 시 트래커 다중선택)
│       └── section_widget.py  ← CbSectionWidget (2,016줄) — 과거차 섹션 패널
│                                ─ accordion_list_mode (실사용) — 트래커 그룹→이슈행→
│                                  상세 아코디언. 미설정 시 단순 텍스트 뷰로 폴백
│                                ─ 미사용 모드 3종(checklist/tracker_list/chip_grid)
│                                  ~800줄 dead code 제거 완료 (2026-06 정리)
│
├── view/                  ← UI 패키지 (호출 측은 `from view.ui_xxx import Y` 명시 경로 사용)
│   ├── __init__.py        ← 패키지 docstring만 — 재수출 없음
│   ├── ui_shell.py        ← MainShell + Sidebar + ArrowLabel — 9탭 좌측 사이드바 + 페이지 스택
│   ├── ui_md.py           ← 마크다운 → HTML 변환 (Qt 의존없음)
│                            ─ ``` (언어 힌트 없음) → 라이트 슬레이트 콜아웃 (발생 시나리오)
│                            ─ ```c / ```cpp 등 → 다크 코드 블록 (기존 동작)
│                            ─ 표 셀 word-break:keep-all (한글 어절 유지)
│                            ─ td code 톤다운 (옅은 슬레이트 배지) — SA 표 가독성
│                            ─ [CERT-C] / [MISRA-C:YYYY] 표준 태그 앞 줄바꿈 자동
│                            ─ **한글로 시작하는 대괄호** (`[변수 삭제]`) 앞에 자동 `<br>` —
│                              주의: 결함 분류 셀에서는 한글 대괄호 사용 금지
│                              (sys_vuln_template.md 의 결함 분류 형식이 자동 줄바꿈에 안 걸리도록 설계됨)
│   ├── ui_save.py         ← AI 분석 결과 저장 (MD/HTML/DOCX)
│   │                        ─ DOCX: _md_to_docx 마크다운 파서 → 헤더(Heading 1~4),
│   │                          실제 Word 표(Light Grid Accent 1), 코드블록 음영,
│   │                          인라인 bold/code/italic 서식 (ui_md 와 동일 규칙 포팅)
│   │                        ─ show_save_popup(parent, anchor_btn, ...) — anchor_btn 기준으로
│   │                          MD/HTML/DOCX/모두 저장 메뉴 위치 결정
│   ├── ui_diff_export.py  ← 코드 변경점(DIFF) Excel/HTML 내보내기
│   │                        ─ Excel: openpyxl write_only + NamedStyle (셀 단위 스타일
│   │                          비용 제거 — 기존 5~15× 단축, 출력 형식 동일)
│   │                        ─ 폴더 모드 다중 파일: ThreadPoolExecutor 로 병렬 저장
│   │                          (max_workers=min(8, cpu)). 출력 경로는 메인 스레드에서
│   │                          미리 계산해 파일명 충돌 방지
│   │                        ─ QProgressDialog 진행률 + 취소 버튼, processEvents() 로
│   │                          UI 무응답 방지
│   ├── ui_cb_upload.py    ← CbUploadDialog — AI 결과 → Codebeamer 업로드 다이얼로그
│   │                        ─ 트래커 URL/ID 입력 (직전 사용값 자동 채움)
│   │                        ─ 새 이슈 / 기존 이슈 코멘트 라디오 + (코멘트 모드) 이슈 ID
│   │                        ─ MD/HTML 첨부 체크박스 + 제목 미리보기
│   ├── ui_input.py        ← 좌측 InputPanel (+ _AppHeader 내부 헬퍼)
│   │                        — 현재 9탭 구조에서는 일부만 사용 (ResultPanel/페이지 들이 흡수)
│   ├── ui_result.py       ← 우측 ResultPanel + 보조 위젯 (~2,966줄 — 가장 큰 view 파일)
│   │                        ─ "📤 CB 업로드" 버튼 추가 (💾 결과물 저장 옆)
│   │                        ─ cb_upload_clicked 시그널 → main.py 가 cb._on_cb_upload 에 연결
│   │                        ─ _show_save_popup(anchor_btn=None) — None 이면 내부 _save_btn,
│   │                          외부 헤더 버튼 전달 시 그 위치 기준 (ReviewPage 헤더에서 사용)
│   │                        ─ ⚠ ExtrasPanel._req_tab 은 None 만 초기화되고 인스턴스화 안 됨
│   │                          (요구사항 입력은 SRS 페이지로 이동 — AUDIT_TODO.md H5 참조)
│   ├── ui_dialog.py       ← DiffLoadingDialog + SrsAnalysisProgressDialog + 기타 다이얼로그
│   ├── extras_sections.py ← ExtrasPanel 의 추가 분석 자료 섹션 위젯들
│   └── pages/             ← 9탭 페이지 각각 분리
│       ├── __init__.py
│       ├── _common.py     ← PageHeader (페이지 헤더 + 저장/업로드 버튼) + BasePage +
│       │                    TabBar + TabStack — 모든 페이지가 상속/사용
│       ├── page_placeholder.py
│       │                  ← 미구현 페이지 placeholder (StaticResultPage, TestResultPage,
│       │                    OpenItemsPage, DeployReviewPage) — 임시 자리채움
│       ├── page_spec.py   ← ① 사양 변경 페이지 (SpecChangePage)
│       │                    ─ 변경점 묶음별 [📤 등록] / 헤더 [📤 전체 등록] (CB 일괄 업로드)
│       │                    ─ change_register_requested / change_register_all_requested 시그널
│       ├── page_swe.py    ← ② SWE.1 SRS (SrsPage), ③ SWE.2 SAD (SadPage),
│       │                    ④ SWE.3 SDD (SddPage) 정의
│       ├── page_srs_review_panel.py
│       │                  ← SrsPage 에 임베드되는 SRS 검토 워크플로우 위젯 3종
│       │                    (CbHistoricalSubTab / ChecklistReviewSubTab / AiResultDropdownPanel)
│       └── page_review.py ← ⑥ 코드리뷰 결과 페이지 (ReviewPage) — ResultPanel 통째로 임베드,
│                            INPUT/OUTPUT 2단계 + 서브탭 구조로 재포장
│
├── prompts/               ← 외부화된 프롬프트 MD
│   ├── CERT_C_Rules_Summary.md         ← cert_c 옵션 체크 시 컨텍스트로 주입
│   ├── MISRA_C_Rules_By_Priority_2012.md   ← misra_c 옵션
│   ├── MISRA_C_Rules_By_Priority_2023.md   ← misra_c23 옵션
│   ├── SW_Quality_Categories.md       ← ⭐ cat1~cat6 카테고리 정의 (항상 user body 에 주입)
│   │                                     단순/복합 6개 카테고리 + 20개 유형 상세 예시.
│   │                                     core.worker.BASE_CONTEXT_FILES 의 "sw_quality" 키
│   ├── checklists/
│   │   └── srs_review_default.json    ← SRS 검토 기본 체크리스트
│   └── system/                        ← 시스템 프롬프트 (코드에서 _load() 로 읽음)
│       ├── sys_summary.md             (_SYS_SUMMARY) — 변경점 요약 프롬프트
│       ├── sys_vuln_template.md       (_SYS_VULN_TMPL) — 취약점 분석 프롬프트
│       │                              플레이스홀더: {cats}/{rule_violation_section}/
│       │                              {past_issue_section}/{sa_standards_principle}/
│       │                              {sa_crossref_rule}/{sa_summary_note}/{sa_table_column}/
│       │                              {sa_selfcheck_crossref}/{sa_selfcheck_heading}/{req_principle}
│       │                              ─ 결함 분류 셀 형식: `단순/복합 — 카테고리명 — 유형 N: 유형명`
│       │                                (한글 대괄호 사용 금지 — ui_md 자동 줄바꿈 방지)
│       │                              ─ 위치 셀 형식: `파일 \`파일명\`, 함수 \`함수명()\`, 라인 N`
│       │                                (세 항목 모두 필수)
│       ├── rule_violation_section.md  (_RULE_VIOLATION_SECTION — {standards})
│       │                              ─ 규칙 ID 백틱·표준 태그·줄바꿈 가이드 포함
│       ├── cb_issues_section.md       (_CB_ISSUES_SECTION) — 과거차 이슈 경고 출력 섹션
│       ├── cb_vuln_section.md         (_CB_VULN_SECTION) — Codebeamer 이슈 검사 지시
│       ├── requirement_mapping_section.md
│       │                              ← 요구사항-코드 매핑 섹션 (req_text 제공 시 사용)
│       └── srs_review.md              ← SRS 검토 시스템 프롬프트 (srs_review_v2_worker 가 사용)
│
├── assets/                ← 정적 리소스 (Image.jfif 등)
├── docs/                  ← 문서 (버전관리.txt, color_reference.html)
│
├── CLAUDE.md              ← 본 파일 (Claude 가이드)
├── README.md              ← 외부 사용자 가이드
├── AUDIT_TODO.md          ← 코드 감사 결과 TODO 리스트 (점진적 개선용 — HIGH/MID/LOW 우선순위)
├── requirements.txt       ← Python 의존성
├── cb_config.json         ← Codebeamer 자격증명 (사용자 데이터, 루트 유지)
├── CodeReviewer.spec      ← PyInstaller 빌드 스펙 (변형: AI_CodeReview*.spec)
├── build/, dist/          ← PyInstaller 산출물
└── __pycache__/
```

## 9탭 사이드바 구조 (좌측 셸 — MainShell)

| # | 키 | 페이지 클래스 | 역할 |
|---|---|---|---|
| ① | spec   | SpecChangePage     | 사양 변경 — 변경점 묶음별 CB 등록 |
| ② | srs    | SrsPage            | SWE.1 (요구사항 DIFF + 검토 체크시트) |
| ③ | sad    | SadPage            | SWE.2 (시스템 아키텍처 설계) |
| ④ | sdd    | SddPage            | SWE.3/4 (소프트웨어 상세 설계) |
| ⑤ | static | StaticResultPage   | 정적분석 결과 (placeholder) |
| ⑥ | review | ReviewPage         | ⭐ 코드리뷰 결과 (AI 분석 메인 페이지) |
| ⑦ | test   | TestResultPage     | 테스트 결과 (placeholder) |
| ⑧ | open   | OpenItemsPage      | 오픈 이슈 (placeholder) |
| ⑨ | deploy | DeployReviewPage   | 배포 검토 (placeholder) |

⑥ 페이지가 AI 분석 메인 — 다른 placeholder 페이지들은 헤더 저장/CB 업로드 버튼이 상태바 안내만 표시.

## 모듈 의존성 흐름

```
main.py
  ├→ config
  ├→ view.ui_shell (MainShell — 9탭 사이드바)
  ├→ view.pages.* (페이지별 클래스)
  ├→ view.ui_diff_export
  ├→ controllers (CbController, DiffController, AiController, SrsReviewV2Controller)
  └→ InputShim / ResultShim (컨트롤러 호환 어댑터)
        │  ↑ MainWindow 자기 자신을 인자로 주입 (ui_save 패턴)
        │
        ├ controllers.cb_controller         → integrations.codebeamer
        ├ controllers.diff_controller       → core.model, core.text_io,
        │                                     workers.diff_worker, view (DiffLoadingDialog)
        ├ controllers.ai_controller         → core.worker (BASE_CONTEXT_FILES,
        │                                     OPTION_MD_FILES), workers.prompts_worker
        └ controllers.srs_review_v2_controller → workers.srs_review_v2_worker

                                          ↘ 컨트롤러 간 호출:
                                             ai → diff (changed_text, build_folder_code_parts)
                                             ai → cb  (cb_context, load_sections)

workers.prompts_worker     → core.worker  (CAT_PROMPTS, _SYS_* 시스템 프롬프트 import)
workers.cb_upload_worker   → integrations.codebeamer.api (CbFetcher), view.ui_md
workers.cb_bulk_upload_worker → integrations.codebeamer.api
workers.srs_review_v2_worker → prompts/system/srs_review.md + prompts/checklists/*.json

view.*                    → core.model, integrations.codebeamer
view.pages.*              → view.ui_result (ReviewPage 가 임베드), view.ui_*, config
```

* main.py 는 위젯을 만들고 `_input.diff_clicked.connect(self._diff.on_diff)` 같은 시그널 와이어링만 한다 — 비즈니스 로직 직접 보유 X.
* InputShim / ResultShim 은 컨트롤러가 기대하는 단일 InputPanel / ResultPanel 인터페이스를, 9탭으로 분산된 페이지 위젯들에 매핑하는 어댑터.
* controllers/ 는 평범한 (대부분 Qt 비의존) 클래스로, MainWindow 를 약한 의존(`self._mw`)으로 보유한다. 컨트롤러 간 호출은 단방향 (AI → DIFF, AI → CB).
* core 는 외부 라이브러리(anthropic 등) 와 Qt 모두 의존하지 않는 순수 로직층.
* workers 는 Qt QThread 기반 백그라운드 작업 — anthropic/requests 호출 지점.
* view 는 Qt UI 위젯 + 저장/내보내기 헬퍼 모듈 — core/integrations 결과를 표시.
* integrations 는 외부 API 어댑터 — Qt 일부 사용 (설정 다이얼로그).

## 분석 컨텍스트 파일 흐름 (Claude API 입력)

코드 리뷰 분석 시 user message body 에 들어가는 컨텍스트 문서들이 어디서 어떻게 조립되는지:

```
ai_controller.on_ai
  ↓ ① BASE_CONTEXT_FILES 로드 (항상 — 체크박스 무관)
  │    └→ sw_quality → prompts/SW_Quality_Categories.md (cat1~cat6 정의)
  ↓ ② OPTION_MD_FILES 로드 (opts dict 에서 체크된 것만)
  │    └→ cert_c / misra_c / misra_c23 / req_diff
  ↓ option_contents dict 완성
  ↓
ReviewWorker._body()
  ↓ option_contents 각 항목을 user body 에 "=== <LABEL> ===\n<content>\n" 형태로 추가
  │  └→ sw_quality → "=== SW 품질 결함 카테고리 기준 ==="
  │  └→ cert_c     → "=== CERT-C 규칙 기준 (...) ==="
  ↓
Claude API 호출
  • system prompt (sys_vuln_template.md): {cats} 자리에 cat1~cat6 stub 6개가 들어감.
    각 stub 은 user body 의 "=== SW 품질 결함 카테고리 기준 ===" 섹션을 참조하도록 지시
    (cert_c / misra_c 와 동일 패턴)
  • user body: 변경점 코드 + 카테고리 정의 + 선택 표준 규칙 + (요구사항 / CB 컨텍스트)
```

## 핵심 설계 패턴

### 1. BASE vs OPTION 컨텍스트 분리
- **BASE_CONTEXT_FILES** (`core/worker.py`): 항상 로드되는 분석 기준 — 룰북. 새 기본 컨텍스트 추가 시 여기에만 추가.
- **OPTION_MD_FILES** (`core/worker.py`): 사용자가 체크해야만 로드되는 표준/요구사항 — 확장팩. 새 옵션 추가 시 여기에만 추가.

### 2. cat 카테고리 stub 패턴 (cert_c / misra_c 동형)
- `CAT_PROMPTS["catN"]` 는 짧은 stub (4줄) — "user body 의 카테고리 기준 섹션을 참고해서 검사하라" 지시만 보유
- 실제 카테고리 본문은 `prompts/SW_Quality_Categories.md` 에 외부화
- 카테고리 추가/삭제 시 3곳 동기화: (1) MD 파일 (2) `CAT_PROMPTS` stub (3) `prompts_worker.BASE_KEYS`

*코드 수정 시, 수정한 부분 알려주기
