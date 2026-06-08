# 🔍 코드 감사 TODO 리스트

> **생성일**: 2026-05-26 (Claude 코드 감사 결과 정리)
> **검토 범위**: 전체 ~20,400줄 (controllers + main + core + workers + view + view/pages + integrations)
> **총 발견 항목**: 77개 (🔴 HIGH 11 / 🟡 MID 37 / 🟢 LOW 29)
> **예상 LOC 절감**: ~1,500줄 (HIGH+MID 정리 시, 전체 약 7%)
>
> ✏️ 진행 시 각 항목 앞 `[ ]` → `[x]` 로 체크, 작업 메모는 항목 아래 들여쓰기.

---

## ✅ 완료된 항목 (최근)

- **2026-05-26**: M28 (tab_panel.py 제거) — `tab_panel.py` 파일 + `view/ui_result.py:31` import + `__init__.py` 재수출/docstring + CLAUDE.md / README.md 언급까지 모두 정리. M30 (CbTabPanel 재수출) 함께 처리.

---

## 🎯 작업 묶음 (Pack) — 권장 진행 순서

| Pack | 묶음 내용 | 항목 | LOC 절약 | 위험도 | 추천 |
|---|---|---|---|---|---|
| **🅴** | 미사용 import + stale docstring + dead 분기 | M20~M24, M3, D계열 | ~60줄 | 🟢 낮음 | ⭐ 1순위 |
| **🅲** | `[대화형AI DISABLED]` 일괄 정리 | H2, M8, M17, M18 | ~250줄 | 🟢 낮음 | ⭐ 2순위 |
| **🅰** | HIGH 버그 수정 | H1, H3, H4, H5~H7, H8 | - | 🟡 중간 | ⭐ 3순위 |
| **🅱** | section_widget 미사용 모드 | M26, M27, M29 | ~700줄 | 🟡 중간 | 4순위 |
| **🅳** | ui_result.py dummy/dead 메서드 + StepBar | M15, M16, M19 | ~200줄 | 🟡 중간 | 5순위 |
| **🅵** | 매직 넘버 / 다이얼로그 보일러플레이트 (LOW) | L계열 | ~300줄 | 🟢 낮음 | 시간 될 때 |

---

## 🔴 HIGH (11개) — 실제 버그 / 안전성 영향

### controllers + main.py

- [ ] **H1** `controllers/ai_controller.py:189` — DIFF 추출 안 한 채 AI 실행 시 `mw._diff.changed_text=""` → 빈 컨텍스트로 분석
  - **권장**: `on_ai` 진입부에 `if not mw._diff.changed_text: 상태바 경고; return` 가드 추가

- [ ] **H2** `controllers/ai_controller.py:1009-1130` — `[대화형AI DISABLED]` ~120줄 블록 (Pack 🅲 와 함께)
  - **권장**: `workers/prompts_worker.py:411-505` + `view/ui_result.py` 의 채팅 흐름과 함께 통째로 삭제

### core + workers

- [ ] **H3** `core/model.py:43-53` — `_remove_comments` 의 문자열 처리에서 char literal 경계 미흡 → 줄번호 어긋남 가능
  - **권장**: C char literal 패턴 (`'\X'`/`'X'`) 만 허용하거나 길이 제한 검출 추가

- [ ] **H4** `core/model.py:390 vs 505-508` — `diff_func_analysis` 는 공백 라인 차이를 변경으로 봄, `find_changed_functions` 는 무시 → 같은 입력에 다른 함수 집합
  - **권장**: 두 함수의 globals 비교 정책 통일 (공백 무시 또는 엄격 비교 한쪽으로)
  - **메모**: 직전에 input 통일은 했지만 내부 로직 차이는 남아있음

### view/ui_*.py

- [ ] **H5** `view/ui_result.py:924, 1118-1136` — `ExtrasPanel._req_tab = None` 만 초기화, 인스턴스화 안 됨 → `get_req_text()` 항상 `""` → AI 가 요구사항 영원히 못 봄
  - **권장**: 요구사항이 SRS 페이지로 이동했다면 `extras_panel.get_req_text()` 호출부를 `srs_page.get_text()` 로 교체
  - **연관**: H6, H7, M34

- [ ] **H6** `view/ui_result.py:817-895` — `_ReqTabContent` 클래스 정의는 있으나 인스턴스화 0건
  - **권장**: H5 해결 후 클래스 통째로 삭제

- [ ] **H7** `main.py:412 ↔ view/ui_result.py:1747, 882` — `req_diff_requested` 시그널 emit 지점 도달 불가 (H6 의 결과)
  - **권장**: H5/H6 해결 시 함께 정리

### view/pages + integrations

- [ ] **H8** `integrations/codebeamer/dialogs.py:25` — `CbConfigDialog.context_updated` 시그널 선언 + `cb_controller.py:47` connect 됐지만 emit 0건
  - **권장**: emit 누락 버그 확인 (CB 설정 변경 후 동기화가 동작 안 하는지) — 동작 필요하면 emit 추가, 불필요하면 시그널 제거

- [ ] **H9** `integrations/codebeamer/api.py:209-211` — `create_item` strategy 루프가 HTTP 400 외 에러 시 즉시 break → strategy 2~6 도달 불가 가능
  - **권장**: 어떤 HTTP 코드에서 다음 strategy 시도할지 정책 명시 (404/500도 다음으로 진행?)

- [ ] **H10** `integrations/codebeamer/config.py:39-49` — `TRACKER_DEFS` 에 사이트별 9개 트래커 ID 하드코딩
  - **권장**: `cb_config.json` 으로 이동 (사이트 변경 시 코드 수정 없이 대응)

- [ ] **H11** `integrations/codebeamer/api.py:13` — `urllib3.disable_warnings` + `session.verify=False`
  - **권장**: README/주석에 사유(사내 자체서명 인증서 등) 명시

---

## 🟡 MID (37개)

### controllers + main.py (7개)

- [ ] **M1** `main.py:202-203, 219-220, 222-223` — `InputShim` 의 `update_cb_status / set_analysis_panel / set_include_opt` no-op
  - **권장**: 호출 측 (`cb_controller.on_connected` 등) 에서 호출 제거

- [ ] **M2** `main.py:419-420` — `result.include_changed → input.set_include_opt` 양방향 connect 인데 한쪽이 no-op
  - **권장**: 해당 connect 한 줄 제거

- [ ] **M3** `controllers/ai_controller.py:77, 89-92` — `_UNIMPLEMENTED = set()` 항상 빈 집합인데 `if key in _UNIMPLEMENTED:` 분기 존재
  - **권장**: 통째로 삭제 (extra1 비활성화 영구 → 분기 자체 무의미)

- [ ] **M4** `controllers/ai_controller.py:119, 149` — `import sys`, `QApplication` 함수 내부 매 호출마다 import
  - **권장**: 파일 상단으로 이동

- [ ] **M5** `controllers/cb_controller.py:29-34` — `_SECTION_TITLES` 사실상 1줄짜리 (`past` 만 남음)
  - **권장**: 인라인 처리

- [ ] **M6** `controllers/cb_controller.py:105-106` — `hasattr(mw._result, "_sum_view")` 가 항상 True (ResultShim 위임)
  - **권장**: hasattr 체크 제거

- [ ] **M7** `controllers/ai_controller.py:208` — `_on_summary` 의 `truncated: bool = False` default 무의미 (시그널이 2-인자 emit)
  - **권장**: default 제거

### core + workers (7개)

- [ ] **M8** `workers/prompts_worker.py:411-505` — `[대화형AI DISABLED]` ~93줄 (`_SYS_CHAT` + `QaWorker`)  *(Pack 🅲)*
  - **권장**: H2 와 함께 일괄 삭제

- [ ] **M9** `workers/cb_upload_worker.py:97`, `workers/cb_bulk_upload_worker.py:190` — `tempfile.mkdtemp` 만들고 안 지움 → 임시 폴더 누적
  - **권장**: `try/finally + shutil.rmtree(tmp, ignore_errors=True)` 패턴 추가

- [ ] **M10** `workers/__init__.py:1-7` — docstring 이 cb_upload/cb_bulk/srs_review 누락
  - **권장**: 갱신 또는 한 줄로 축약

- [ ] **M11** `core/__init__.py:1-7` — docstring 이 `text_io.py` 누락
  - **권장**: 갱신

- [ ] **M12** `workers/cb_upload_worker.py:64-69` — `_md_to_html` 실패 시 폴백 주석은 "PlainText" 인데 코드는 `Html` 로 보냄
  - **권장**: 폴백 시 `description_format="PlainText"` 로 분기 또는 주석 정정

- [ ] **M13** `workers/diff_worker.py:143-144` — `def read_lines(path): return read_text_lines(path)` 의미 없는 래퍼
  - **권장**: 직접 `read_text_lines` 호출로 단순화

- [ ] **M14** `workers/cb_upload_worker.py:30` — `extra_attachments: list = None` 잘못된 타입 힌트
  - **권장**: `list | None = None` 으로 변경

### view/ui_*.py (11개)

- [ ] **M15** `view/ui_result.py:744-781` — `AnalysisFilePanel` dead 메서드 8종 (`_build_file_card, _build_req_card, _switch_inner, _load_cb_data, refresh_cb_data, _card_frame, _refresh_cb, _switch_req_mode`) ~40줄
  - **권장**: 일괄 삭제 (외부 호출 0건 확인됨)

- [ ] **M16** `view/ui_result.py:2447-2460` — `_show_single_file` 호출처 없음 (`_ensure_folder_file_in_diff` 로 대체됨)
  - **권장**: 삭제

- [ ] **M17** `view/ui_result.py:1620-1621, 1763-1765, 2643, 2727-2789, 2934-2938` — `[대화형AI DISABLED]` ~80~100줄  *(Pack 🅲)*
  - **권장**: H2/M8 과 함께 일괄 삭제

- [ ] **M18** `view/ui_result.py:2797-2800` — `update_vuln_text` 호출처는 비활성 채팅 흐름 뿐  *(Pack 🅲)*
  - **권장**: H2/M8/M17 과 함께 정리

- [ ] **M19** `view/ui_result.py:1714-1716, 2046, 2300, 2335, 2642, 2794, 2923` — `StepBar` ~85줄 — `hide()` 된 채 `advance/spotlight` 만 호출 → 시각 효과 0
  - **권장**: 클래스(85-174줄) + 모든 호출부 함께 정리

- [ ] **M20** `view/ui_result.py:19-31` — 미사용 import (CbTabPanel 은 이미 제거됨, 나머지 10개: `QApplication, QDialog, QGridLayout, QMessageBox, QPixmap, QLineEdit, QProgressBar, build_unified_diff, hsep, sec_label`)  *(Pack 🅴)*
  - **권장**: 정리

- [ ] **M21** `view/ui_dialog.py:10` — `QScrollArea` 미사용 import  *(Pack 🅴)*
  - **권장**: 정리

- [ ] **M22** `view/ui_save.py:230-233, 252` — `Inches, OxmlElement` 미사용 + `qn` 252줄 중복 import  *(Pack 🅴)*
  - **권장**: 정리

- [ ] **M23** `view/ui_input.py:49, 62, 73` — `[DISABLED]` 이스터에그 흔적 3줄  *(Pack 🅴)*
  - **권장**: 안내 문구 1개만 남기고 정리

- [ ] **M24** `view/__init__.py:6-9` — docstring 이 `ui_input, ui_shell, ui_cb_upload, extras_sections` 누락  *(Pack 🅴)*
  - **권장**: 갱신

- [ ] **M25** `view/ui_result.py:922, 971` — `_chk_widgets` 와 `_include_chks` 가 동일 QCheckBox 인스턴스 중복 보관
  - **권장**: 한쪽 dict 제거

### view/pages + integrations (12개)

- [x] ~~**M26** `integrations/codebeamer/section_widget.py:60` — `_CHIP_GRID_COLS = 4` 로컬 변수 미참조~~ ✅ **완료 (2026-06-05)** *(Pack 🅱)*

- [x] ~~**M27** `integrations/codebeamer/section_widget.py:1735~2155` — `checklist_mode` 본체 ~420줄 (호출처 0건)~~ ✅ **완료 (2026-06-05)** *(Pack 🅱)*

- [x] ~~**M28** `integrations/codebeamer/tab_panel.py` 전체 116줄~~ ✅ **완료 (2026-05-26)**
  - 파일 삭제 + `view/ui_result.py:31` import 제거 + `__init__.py` 재수출/docstring 정리 + CLAUDE.md / README.md 언급 삭제

- [ ] **M29** `integrations/codebeamer/section_widget.py:48~74, 2220~2477, 2541~2611` — `tracker_list_mode`, `chip_grid_mode` 분기 ~250줄  *(Pack 🅱)*
  - **권장**: 삭제

- [x] ~~**M30** `integrations/codebeamer/__init__.py:14, 23, 42, 54` — `CbTabPanel` 재수출~~ ✅ **완료 (2026-05-26)** (M28 과 함께)

- [ ] **M31** `integrations/codebeamer/config.py:39-49 + 56-60` — `TRACKER_DEFS` 자동 삽입 + `section_widget.py:2189` 의 "자동 삽입 제거" 주석 충돌
  - **권장**: 의도 확인 후 한쪽 정리 (H10 과 연관)

- [ ] **M32** `integrations/codebeamer/config.py:57-58` — `tracker_X` 키 저장 — legacy 폴백 한 곳에서만 사용
  - **권장**: dead legacy key — 제거

- [ ] **M33** `view/pages/_common.py:1-7` — docstring 이 `InOutTabs, SubTabs` 라고 적혔지만 실제는 `TabBar, TabStack`  *(Pack 🅴)*
  - **권장**: 갱신

- [ ] **M34** `view/pages/page_review.py:48-50` — "ExtrasPanel 인스턴스는 컨트롤러 호환을 위해" 주석 (H5 와 연관)
  - **권장**: H5 해결 시 함께 정리

- [ ] **M35** `integrations/codebeamer/section_widget.py:2189` — 주석 ("자동 삽입 제거") 과 실제 동작 불일치
  - **권장**: M31 과 함께 정리

- [ ] **M36** `view/pages/page_swe.py:62-63` — 타입 어노테이션 위치 일관성
  - **권장**: `"ReqInput | None"` 등 문자열 어노테이션 통일

- [ ] **M37** `view/pages/page_srs_review_panel.py:1115` — `_build` 가 `fully_external` 분기에서 early return — 가독성 ↓
  - **권장**: 별도 메서드로 분리

---

## 🟢 LOW (29개) — 선택적 개선

### controllers + main.py (8개)

- [ ] **L1** `controllers/ai_controller.py:30` — 매직 넘버 `16000` → `_DEFAULT_MAX_TOKENS` 상수화
- [ ] **L2** `controllers/ai_controller.py:394-396` — `MODEL_LIMIT = 200_000`, `BUFFER = 20_000` 함수 로컬 → 모듈 상수화
- [ ] **L3** `controllers/ai_controller.py:443-622, 650-790, 845-1002` — 4개 다이얼로그 보일러플레이트 ~300줄 → 베이스 다이얼로그 추출
- [ ] **L4** `controllers/cb_controller.py:170, 192-209, 300, 302-321` — 워커 스핀 보일러플레이트 → `_spawn_upload_worker` 헬퍼
- [x] ~~**L5** `controllers/srs_review_controller.py:241-245` — 중첩 try/except silent~~ ✅ **무효 (파일 삭제됨, v1 SRS 정리)**
- [ ] **L6** `controllers/cb_controller.py:177, 181, 243, 261, 367, 406` — broad `except Exception` 패턴 → 한 줄 코멘트 권장
- [ ] **L7** `controllers/diff_controller.py:39` — `_diff_thread/_worker/_dlg` 종료 시 None 재설정 없음 → 라이프사이클 일관성
- [ ] **L8** `controllers/ai_controller.py:266-283` — `_API_KEY_MARKERS`, `_TOKEN_LIMIT_MARKERS` 함수 로컬 → 모듈 상수

### core + workers (5개)

- [ ] **L9** `core/model.py:79-88` — `r'^[\s]*'` → `r'^\s*'` (`[\s]` 불필요)  *(Pack 🅴)*
- [ ] **L10** `core/model.py:217-220` — 단일 라인 함수 본문 전체가 시그니처로 잡힘 (표시 외 영향 없음)
- [x] ~~**L11** `workers/srs_review_worker.py:205` — `re.IGNORECASE` 플래그~~ ✅ **무효 (파일 삭제됨, v1 SRS 정리)**
- [ ] **L12** `core/worker.py:30` — `req_diff` 미구현 키 — ai_controller 흐름 점검 권장
- [ ] **L13** `core/model.py:262` — `func_ranges: set` 어노테이션 → `set[int]` 명시

### view/ui_*.py (8개)

- [ ] **L14** `view/ui_diff_export.py:457` — `if hasattr(os, 'path')` 항상 True — 데드 가드
- [ ] **L15** `view/ui_diff_export.py:462` — `rel_path = "전체 변경점"` 이후 미사용 변수
- [ ] **L16** `view/ui_diff_export.py:307-328` — `build_html_file_section` 외부 호출 없음 → 삭제
- [ ] **L17** `view/ui_result.py:73-79` — `TAB_COLORS` 의 `files/extras` 키 미사용
- [ ] **L18** `view/ui_result.py:38-60` — `_get_check_icon_path` 가 SVG 파일 매번 쓰는 부수효과 → 정적 자산 직접 참조
- [ ] **L19** `view/ui_save.py:107` — `_show_no_result_dialog` 톤이 `ui_dialog` 와 비일관
- [ ] **L20** `view/ui_dialog.py:1336` — `SrsAnalysisProgressDialog.closeEvent` 에서 cancel 시그널 누락
- [ ] **L21** `view/ui_input.py:99-101` — `_cb_test_finished` 시그널 패턴 → `QMetaObject.invokeMethod` 더 명료

### view/pages + integrations (8개)

- [ ] **L22** `view/pages/_common.py:148-185` — `TabStack.changed` 시그널 외부 connect 없음
- [ ] **L23** `integrations/codebeamer/api.py:146, 257, 285, 462` — `import sys` 함수 내부 4곳 → 상단으로
- [ ] **L24** `integrations/codebeamer/api.py:254-274 vs 296-316` — `_check_parent_set` ↔ `set_parent` 내부 `_verify_parent_set` 클로저 중복 → 재사용
- [ ] **L25** `integrations/codebeamer/section_widget.py:2189` — 주석과 실제 동작 불일치 (M35 와 연관)
- [ ] **L26** `view/pages/page_spec.py:762` — `"date": ""` 주석에 "날짜 항목 제거됨" 명시 → 키 자체 제거 가능
- [ ] **L27** `integrations/codebeamer/section_widget.py:1564` — "링크 버튼 미구현 — 추후 구현" 주석 (트래킹)
- [ ] **L28** `integrations/codebeamer/api.py:561-583` — `find_tracker_id` 가 동일 endpoint 두 번 시도 (결과 동일) → 한 번이면 충분
- [ ] **L29** `integrations/codebeamer/dialogs.py:133-134` — `_close_btn 더 이상 사용 안 함` 주석 → 속성 자체 제거 가능

---

## 📊 통계 요약

```
        controllers   core/      view/      view/pages
        + main.py     workers    ui_*.py    + integrations    합계
─────────────────────────────────────────────────────────────────
HIGH       2            2          3            4              11
MID        7            7         11           12              37
LOW        8            5          8            8              29
─────────────────────────────────────────────────────────────────
합계      17           14         22           24              77
완료       0            0          0            2 (M28, M30)    2
남은      17           14         22           22              75
```

**예상 LOC 절감 (HIGH+MID 정리 시)**:
- ~~tab_panel.py + CbTabPanel 재수출~~ ✅ 약 116줄 절감 완료
- section_widget.py 미사용 모드 (M27, M29): ~700줄
- `[대화형AI DISABLED]` 블록 (H2 + M8 + M17 + M18): ~250줄
- AnalysisFilePanel dummy + StepBar + _show_single_file (M15, M16, M19): ~200줄
- 미사용 import + stale docstring + 기타 (M20~M25, M33 등): ~60줄
- **남은 절감 ~1,210줄** (전체 ~20,400줄 중 추가 약 6% 감소 가능)

---

## 📝 작업 메모 영역

> 각 Pack 진행 시 여기에 결과 / 발견 사항 / 후속 작업 기록.

### Pack 🅴 (미사용 import + stale docstring)
- 시작일:
- 완료일:
- 메모:

### Pack 🅲 (`[대화형AI DISABLED]` 일괄 정리)
- 시작일:
- 완료일:
- 메모:

### Pack 🅰 (HIGH 버그 수정)
- 시작일:
- 완료일:
- 메모:

### Pack 🅱 (section_widget 미사용 모드)
- 시작일: 2026-05-26 (부분 — tab_panel.py 만 완료)
- 완료일: (M27/M29 남음)
- 메모: M28 (tab_panel.py 파일/import/__init__/docstring) + M30 (CbTabPanel 재수출) 완료. section_widget.py 의 checklist_mode / tracker_list_mode / chip_grid_mode 정리는 별도 진행 필요.

### Pack 🅳 (ui_result.py dummy/dead)
- 시작일:
- 완료일:
- 메모:

### Pack 🅵 (매직 넘버 / 보일러플레이트)
- 시작일:
- 완료일:
- 메모:
