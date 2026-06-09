"""checklist_parser.py — ASPICE 체크리스트 xlsx 파서 + 저장.

대상 파일 형식 (사용자 제공):
  · 시트명: 'Verification Review Report ' (마지막 공백 주의 — 원본 그대로)
  · r4 C6: 리뷰대상 문서명 및 버전 (예: 'NX5 PLBM-Software Requirement Specification(v2.10)')
  · r25~r31: 관련 문서명 및 버전 표 ([1.3 Reference] 와 매칭)
  · r35 헤더: B/No | C/체크리스트 | I/AI가능여부 | J/의견 | K/판정 | L/상세 심사 내용
  · r36~ : 체크리스트 항목 (No 1 ~ 81)

요구사항 목차 ↔ 체크리스트 No 범위 매핑 (사용자 명세):
  · 2.3 Requirements (=HSI)        →  42~48
  · 3.1 Functional Requirement     →  49~54
  · 3.2 Non-func Requirement       →  55~61
  · 4.1 Safety Functional Req      →  62~69
  · 4.2 Safety Non-Functional Req  →  70~78

수정 가능한 컬럼 (load → 사용자 / AI 수정 → save 새 파일):
  · K (col 11): 판정 (OK / OK But / NG / N/A)
  · L (col 12): 상세 심사 내용

Qt 무관 — 순수 openpyxl 기반.
"""

import os
import re
import shutil
from typing import Optional


# ── 시트/셀 좌표 상수 ──────────────────────────────────────────
SHEET_NAME = "Verification Review Report "   # 마지막 공백 원본 그대로
HEADER_ROW = 35     # B35: 'No', C35: '체크리스트', I35: '가능 여부', ...
DATA_START = 36     # 첫 항목 행
DATA_END_MAX = 200  # 최대 검색 행 (실제 끝은 No 가 None 인 행에서 종료)

# 컬럼 인덱스 (1-based)
COL_NO       = 2     # B
COL_CONTENT  = 3     # C — 체크리스트 문항
COL_AI_OK    = 9     # I — AI 분석 가능 여부 (O/X/△)
COL_OPINION  = 10    # J — AI 적용 여부 의견 (작성자 의견)
COL_JUDGE    = 11    # K — 판정 (OK / OK But / NG / N/A)
COL_DETAIL   = 12    # L — 상세 심사 내용

# 메타 셀
META_TARGET_DOC_CELL = "F4"   # r4 C6: 리뷰대상 문서명 + 버전 (예: '...(v2.10)')
META_REF_START_ROW = 27       # r25 라벨 + r26 헤더 + r27~r31 데이터
META_REF_END_ROW   = 31       # 보수적인 상한 (실제 행수는 파일마다 다를 수 있음)
META_REF_NAME_COL  = 3        # C — 산출물 명
META_REF_VER_COL   = 7        # G — 버전

# 요구사항 목차 ↔ 체크리스트 No 범위 매핑
REQ_SECTION_TO_NO_RANGE = {
    "2.3 Requirements (=HSI)":         (42, 48),
    "3.1 Functional Requirement":      (49, 54),
    "3.2 Non-func Requirement":        (55, 61),
    "4.1 Safety Functional Req":       (62, 69),
    "4.2 Safety Non-Functional Req":   (70, 78),
}


# ══════════════════════════════════════════════════════════════
#  데이터 모델 (간단한 dict 기반 — Qt 무관)
# ══════════════════════════════════════════════════════════════
def make_empty_state() -> dict:
    """초기/빈 체크리스트 상태 dict."""
    return {
        "source_path": "",
        "target_doc":  "",   # 리뷰대상 문서명 + 버전 (F4)
        "references":  [],   # [{"name": ..., "version": ...}, ...]
        "items":       [],   # [{"no": int, "content": str, "ai_ok": str,
                             #   "opinion": str, "judge": str, "detail": str}, ...]
    }


# ══════════════════════════════════════════════════════════════
#  파일 로드
# ══════════════════════════════════════════════════════════════
def load_checklist(path: str) -> dict:
    """체크리스트 xlsx 를 읽어 state dict 로 반환.

    파일이 없거나 시트 구조가 다르면 RuntimeError.
    """
    try:
        import openpyxl
    except ImportError as e:
        raise RuntimeError(
            f"openpyxl 미설치 — pip install openpyxl ({e})") from e

    if not os.path.exists(path):
        raise RuntimeError(f"체크리스트 파일을 찾을 수 없습니다: {path}")

    wb = openpyxl.load_workbook(path, data_only=True)
    # 시트명 매칭 — 정확 일치 우선, 그 다음 trim 매칭
    sheet = None
    if SHEET_NAME in wb.sheetnames:
        sheet = wb[SHEET_NAME]
    else:
        for n in wb.sheetnames:
            if n.strip() == SHEET_NAME.strip():
                sheet = wb[n]
                break
    if sheet is None:
        raise RuntimeError(
            f"시트 {SHEET_NAME!r} 를 찾을 수 없습니다. "
            f"존재 시트: {wb.sheetnames}")

    state = make_empty_state()
    state["source_path"] = path

    # ── 메타 1: 리뷰대상 문서명 + 버전 ──────────────────────
    state["target_doc"] = str(sheet[META_TARGET_DOC_CELL].value or "").strip()

    # ── 메타 2: [1.3 Reference] 와 매칭되는 표 ──────────────
    refs = []
    for r in range(META_REF_START_ROW, META_REF_END_ROW + 1):
        nm = sheet.cell(row=r, column=META_REF_NAME_COL).value
        ver = sheet.cell(row=r, column=META_REF_VER_COL).value
        nm_s = str(nm or "").strip()
        ver_s = str(ver or "").strip()
        if nm_s and not nm_s.startswith("*"):
            refs.append({"name": nm_s, "version": ver_s})
    state["references"] = refs

    # ── 본문: 체크리스트 항목 ────────────────────────────────
    items: list = []
    for r in range(DATA_START, DATA_END_MAX + 1):
        no = sheet.cell(row=r, column=COL_NO).value
        if no is None:
            break
        try:
            no_i = int(no)
        except (TypeError, ValueError):
            continue
        items.append({
            "no":      no_i,
            "content": str(sheet.cell(row=r, column=COL_CONTENT).value or "").strip(),
            "ai_ok":   str(sheet.cell(row=r, column=COL_AI_OK).value   or "").strip(),
            "opinion": str(sheet.cell(row=r, column=COL_OPINION).value or "").strip(),
            "judge":   str(sheet.cell(row=r, column=COL_JUDGE).value   or "").strip(),
            "detail":  str(sheet.cell(row=r, column=COL_DETAIL).value  or "").strip(),
        })
    state["items"] = items
    return state


# ══════════════════════════════════════════════════════════════
#  변경사항 반영해서 새 파일 저장
# ══════════════════════════════════════════════════════════════
def save_checklist(state: dict, out_path: str,
                   template_path: Optional[str] = None) -> str:
    """state 의 변경사항을 적용한 xlsx 파일을 out_path 에 저장.

    원본 서식을 유지하기 위해 template_path (또는 state["source_path"]) 의
    xlsx 를 복사해서 K/L 컬럼 (판정/상세) + 메타 셀만 갱신한다.

    Args:
      state         : load_checklist 가 반환한 dict — 사용자/AI 가 수정한 값
      out_path      : 저장할 새 파일 경로
      template_path : 복사 원본 (없으면 state["source_path"] 사용)

    Returns:
      out_path (절대 경로)
    """
    try:
        import openpyxl
    except ImportError as e:
        raise RuntimeError(
            f"openpyxl 미설치 — pip install openpyxl ({e})") from e

    src = template_path or state.get("source_path") or ""
    if not src or not os.path.exists(src):
        raise RuntimeError(
            f"체크리스트 템플릿 파일 없음 — load_checklist 한 원본 또는 "
            f"template_path 가 필요합니다: {src!r}")

    # 원본 복사 후 그 위에 수정 — 서식/이미지/병합 보존
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    if os.path.abspath(src) != out_path:
        shutil.copyfile(src, out_path)

    wb = openpyxl.load_workbook(out_path)
    sheet = None
    if SHEET_NAME in wb.sheetnames:
        sheet = wb[SHEET_NAME]
    else:
        for n in wb.sheetnames:
            if n.strip() == SHEET_NAME.strip():
                sheet = wb[n]
                break
    if sheet is None:
        raise RuntimeError(
            f"저장 대상 시트 {SHEET_NAME!r} 를 찾을 수 없음")

    # ── 메타 1: 리뷰대상 문서명/버전 ────────────────────────
    td = (state.get("target_doc") or "").strip()
    if td:
        sheet[META_TARGET_DOC_CELL].value = td

    # ── 메타 2: 관련 문서 표 (행 수가 부족하면 채울 수 있는 만큼만) ──
    refs = state.get("references") or []
    if refs:
        for i, ref in enumerate(refs):
            r = META_REF_START_ROW + i
            if r > META_REF_END_ROW:
                break
            nm = (ref.get("name") or "").strip()
            ver = (ref.get("version") or "").strip()
            if nm:
                sheet.cell(row=r, column=META_REF_NAME_COL).value = nm
            if ver:
                sheet.cell(row=r, column=META_REF_VER_COL).value = ver

    # ── 본문: K/L 갱신 ────────────────────────────────────────
    # state["items"] 의 no 와 시트의 No 컬럼을 매칭해서 K/L 만 덮어쓰기.
    items_by_no = {it["no"]: it for it in (state.get("items") or [])
                   if isinstance(it, dict) and "no" in it}
    if items_by_no:
        for r in range(DATA_START, DATA_END_MAX + 1):
            no = sheet.cell(row=r, column=COL_NO).value
            if no is None:
                break
            try:
                no_i = int(no)
            except (TypeError, ValueError):
                continue
            it = items_by_no.get(no_i)
            if not it:
                continue
            judge  = (it.get("judge")  or "").strip()
            detail = (it.get("detail") or "").strip()
            # 빈 문자열로 덮어쓰기는 의도적으로 허용 (사용자가 명시적으로
            # 비워둘 수도 있음). 단 None 으로는 덮지 않음.
            sheet.cell(row=r, column=COL_JUDGE).value  = judge
            sheet.cell(row=r, column=COL_DETAIL).value = detail

    wb.save(out_path)
    return out_path


# ══════════════════════════════════════════════════════════════
#  요구사항 섹션 → 체크리스트 No 범위 헬퍼
# ══════════════════════════════════════════════════════════════
def get_no_range_for_section(section_label: str) -> Optional[tuple]:
    """요구사항 목차 라벨로 체크리스트 No 범위 (start, end) 반환.
    매칭 안 되면 None.

    매칭은 prefix 비교 (목차 번호) — 사용자가 적은 정확한 라벨이 아니어도
    '2.3', '3.1' 등 으로 시작하면 첫 매칭 채택.
    """
    s = (section_label or "").strip()
    if not s:
        return None
    # 직접 키 매칭
    if s in REQ_SECTION_TO_NO_RANGE:
        return REQ_SECTION_TO_NO_RANGE[s]
    # 목차 번호 prefix 매칭 (예: "3.1" → "3.1 Functional Requirement")
    m = re.match(r"(\d+\.\d+|\d+)", s)
    if m:
        prefix = m.group(1) + " "
        for key, rng in REQ_SECTION_TO_NO_RANGE.items():
            if key.startswith(prefix):
                return rng
    return None


def get_no_ranges_for_sections(section_labels) -> set:
    """여러 목차 라벨 → 매칭된 모든 체크리스트 No 의 집합.
    AI 분석 대상 No 만 골라낼 때 사용.
    """
    no_set: set = set()
    for s in (section_labels or []):
        rng = get_no_range_for_section(s)
        if rng:
            a, b = rng
            no_set.update(range(a, b + 1))
    return no_set
