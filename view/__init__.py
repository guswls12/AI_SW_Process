"""view — UI 위젯/저장/마크다운 변환 모듈 패키지.

  ui_md.py          — 마크다운 → HTML 변환 (Qt 의존없음)
  ui_save.py        — AI 분석 결과 저장 (MD/HTML/DOCX, 파일명 헬퍼)
  ui_diff_export.py — 코드 변경점(DIFF) Excel/HTML 내보내기
  ui_input.py       — 좌측 InputPanel
  ui_result.py      — 우측 ResultPanel + 보조 위젯 (StepBar, DropZone, ReqInput,
                      AnalysisFilePanel, ExtrasPanel, DiffView, ReqDiffView, ResultView)
  ui_dialog.py      — DiffLoadingDialog (폴더 DIFF 추출 진행률 다이얼로그)

호출 측은 `from view.ui_xxx import Y` 형태로 모듈 경로를 명시한다 (재수출 안 함).
"""
