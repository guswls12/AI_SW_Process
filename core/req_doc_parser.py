"""req_doc_parser.py — 요구사항/아키텍처/SDD 문서 (.docx) 파서.

대상:
  · ② SWE.1 SRS 요구사항서  (요구사항 ID: SwR_IF_/SwR_FR_/SwR_NFR_ 등)
  · ③ SWE.2 SAD 아키텍처서  (아키텍처 ID — 사용자 명세 대기)
  · ④ SWE.3 SDD 상세설계서  (상세설계 ID — 사용자 명세 대기)

공개 함수:
  · parse_version_from_filename(path)   — 파일명에서 버전 추출
                                          (예: "..._2_5.docx" → "v2.5")
  · parse_reference_table(docx_path)    — [1.3 Reference] 표 추출
                                          → [{name, description, version}, ...]
  · parse_requirements(docx_path, start_heading="2.2 Software State Transition")
                                          — 시작 목차부터 끝까지 요구사항 ID 별 분류
                                          → [{section, id, content, ...}, ...]

Qt 무관 — python-docx 기반.
"""

import os
import re
from typing import Optional


# 요구사항 ID 패턴 — SwR_<TAG>_<숫자> (사용자 명세: SwR_IF_001 / SwR_FR_001 / SwR_NFR_002)
# 임의 prefix 와 임의 태그 허용 (확장성).
REQ_ID_RE = re.compile(
    r"\b(?P<id>(?:SwR|SwArch|SwDD|SwRR)_[A-Za-z]+_\d+)\b"
)


# ══════════════════════════════════════════════════════════════
#  파일명 → 버전 추출
# ══════════════════════════════════════════════════════════════
def parse_version_from_filename(path: str) -> str:
    """파일명에 포함된 `_N_M` 패턴을 'N.M' 버전으로 추출.

    예시:
      'NX5_PLBM-Software Requirements Specification_2_5.docx' → 'v2.5'
      '..._3_11.docx' → 'v3.11'

    매칭 안 되면 빈 문자열.
    """
    if not path:
        return ""
    base = os.path.basename(path)
    # 확장자 제거 후 끝쪽 `_숫자_숫자` 우선 매칭 (파일명 내부의 다른 숫자와 충돌 방지)
    stem = os.path.splitext(base)[0]
    # 끝에서 첫 번째 매칭 — `_2_5` 같은 패턴
    m = re.search(r"_(\d+)_(\d+)\b", stem[::-1])
    if m:
        # 역순으로 매칭한 결과 → 다시 뒤집어서 정상 순서
        major = m.group(2)[::-1]
        minor = m.group(1)[::-1]
        return f"v{major}.{minor}"
    # 폴백 — 전체 stem 에서 마지막 `_N_M` 매칭
    m2 = list(re.finditer(r"_(\d+)_(\d+)(?=\D|$)", stem))
    if m2:
        major = m2[-1].group(1)
        minor = m2[-1].group(2)
        return f"v{major}.{minor}"
    return ""


# ══════════════════════════════════════════════════════════════
#  docx 로드 헬퍼
# ══════════════════════════════════════════════════════════════
def _open_docx(path: str):
    """python-docx 의 Document 객체 반환. 실패 시 RuntimeError."""
    try:
        from docx import Document
    except ImportError as e:
        raise RuntimeError(
            f"python-docx 미설치 — pip install python-docx ({e})") from e
    if not os.path.exists(path):
        raise RuntimeError(f"문서 파일을 찾을 수 없습니다: {path}")
    return Document(path)


def _heading_level(paragraph) -> int:
    """단락의 heading 레벨 (1~9) 반환. heading 아니면 0."""
    style = (getattr(paragraph.style, "name", "") or "").lower()
    m = re.match(r"heading\s*(\d+)", style)
    if m:
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return 0
    return 0


def _para_text(paragraph) -> str:
    """단락 텍스트 (양끝 공백 제거)."""
    return (paragraph.text or "").strip()


def _section_number_prefix(text: str) -> str:
    """문단 텍스트가 '2.2 Software State Transition' 같은 형태이면
    '2.2' 만 반환. 아니면 빈 문자열."""
    m = re.match(r"^(\d+(?:\.\d+)*)\b", (text or "").strip())
    return m.group(1) if m else ""


def _is_section_at_or_after(text: str, start_section: str) -> bool:
    """현재 단락의 섹션 번호가 start_section (예: '2.2') 이상인지.

    비교는 (튜플) 비교 — '2.2' >= '2.2', '2.2.1' > '2.2', '3' > '2.2' 등.
    """
    cur = _section_number_prefix(text)
    if not cur:
        return False
    cur_t = tuple(int(x) for x in cur.split(".") if x.isdigit())
    sta_t = tuple(int(x) for x in start_section.split(".") if x.isdigit())
    return cur_t >= sta_t


# ══════════════════════════════════════════════════════════════
#  [1.3 Reference] 표 추출
# ══════════════════════════════════════════════════════════════
def parse_reference_table(docx_path: str,
                          heading_keywords=("reference",)) -> list:
    """문서의 [1.3 Reference] 단원에 있는 표(Document Name|Description|Version/Date)
    를 추출.

    Returns:
      [{"name": str, "description": str, "version": str}, ...]
      매칭 실패 시 빈 리스트.

    매칭 방법:
      1) heading 1~3 중 "1.3" / "Reference" 키워드 포함하는 섹션 찾기
      2) 그 섹션 안에서 다음 heading 까지의 표 중 첫 번째 표 채택
      3) 표 헤더가 'Document Name' / 'Description' / 'Version' 인지 검증
    """
    doc = _open_docx(docx_path)

    body = doc.element.body
    # 단락+표 순서대로 iterate 필요 — python-docx body.iterchildren 사용
    # 1.3 Reference 섹션 시작/끝 단락 인덱스 찾기
    # python-docx 의 doc.paragraphs / doc.tables 는 별개 리스트라 위치 매칭이 어려움 →
    # body XML 의 자식 순서를 그대로 훑어 단락/표 시퀀스 얻기.
    from docx.oxml.ns import qn

    found_ref_section = False
    in_section = False
    captured_table = None

    for child in body.iterchildren():
        tag = child.tag
        if tag == qn("w:p"):
            # 단락
            from docx.text.paragraph import Paragraph
            p = Paragraph(child, doc)
            text = _para_text(p)
            level = _heading_level(p)
            if level > 0:
                # heading — 'reference' 키워드 확인
                low = text.lower()
                if any(kw in low for kw in heading_keywords):
                    in_section = True
                    found_ref_section = True
                    continue
                if in_section:
                    # 다음 heading 시작 — Reference 섹션 끝
                    break
        elif tag == qn("w:tbl") and in_section:
            from docx.table import Table
            tbl = Table(child, doc)
            captured_table = tbl
            break

    if captured_table is None:
        return []

    # 표 파싱 — 헤더 행 (Document Name / Description / Version)
    rows = captured_table.rows
    if not rows:
        return []

    # 헤더 인덱스 찾기 (첫 행 또는 처음 몇 행 안에서)
    header_row_idx = 0
    name_col = None
    desc_col = None
    ver_col  = None
    for hi in range(min(2, len(rows))):
        cells = rows[hi].cells
        for ci, cell in enumerate(cells):
            txt = (cell.text or "").strip().lower()
            if "document name" in txt or txt == "name":
                name_col = ci
            elif "description" in txt:
                desc_col = ci
            elif "version" in txt or "date" in txt:
                ver_col = ci
        if name_col is not None:
            header_row_idx = hi
            break

    if name_col is None:
        # 헤더 매칭 실패 — 기본 3컬럼 가정
        name_col, desc_col, ver_col = 0, 1, 2

    result = []
    for row in rows[header_row_idx + 1:]:
        cells = row.cells
        if not cells:
            continue
        nm = (cells[name_col].text or "").strip() if name_col < len(cells) else ""
        ds = (cells[desc_col].text or "").strip() if desc_col is not None and desc_col < len(cells) else ""
        vr = (cells[ver_col].text or "").strip() if ver_col is not None and ver_col < len(cells) else ""
        if nm:
            result.append({
                "name":        nm,
                "description": ds,
                "version":     vr,
            })
    return result


# ══════════════════════════════════════════════════════════════
#  요구사항 추출 — 시작 목차부터 끝까지 ID 별 분류
# ══════════════════════════════════════════════════════════════
def parse_requirements(docx_path: str,
                       start_heading: str = "2.2") -> list:
    """문서의 start_heading (예: '2.2 Software State Transition') 부터 끝까지
    요구사항 ID 별로 추출.

    Args:
      docx_path     : .docx 파일 경로
      start_heading : 추출 시작 섹션 번호 (예: "2.2") — heading 텍스트의
                      앞 부분에 이 번호가 포함되어 있으면 시작.

    Returns:
      [
        {
          "section":  "2.2 Software State Transition",   # 요구사항이 속한 상단 목차
          "id":       "SwR_IF_001",                      # 요구사항 ID (없으면 "")
          "title":    "...",                             # 요구사항 제목 (heading 텍스트)
          "content":  "본문 텍스트",                       # ID 이후 다음 ID 또는 heading 까지
        }, ...
      ]
    """
    doc = _open_docx(docx_path)
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    sections: list = []
    current_section = ""        # 현재 상단 목차 (예: '2.2 Software State Transition')
    current_id = ""             # 현재 요구사항 ID
    current_title = ""          # 현재 ID 와 함께 잡힌 heading/제목 라인
    buf: list = []              # 현재 요구사항 본문 누적
    started = False             # start_heading 도달 여부

    start_prefix = (start_heading or "").strip().split()[0]   # '2.2' 만

    def _flush():
        nonlocal buf, current_id, current_title
        if started and current_id:
            sections.append({
                "section": current_section,
                "id":      current_id,
                "title":   current_title,
                "content": "\n".join(b for b in buf if b).strip(),
            })
        buf = []

    for child in doc.element.body.iterchildren():
        if child.tag != qn("w:p"):
            continue
        p = Paragraph(child, doc)
        text = _para_text(p)
        level = _heading_level(p)

        # 시작 헤딩 도달 여부
        if not started:
            if level > 0 and _is_section_at_or_after(text, start_prefix):
                started = True
                current_section = text
            else:
                continue

        # 시작 이후
        if level > 0:
            # 헤딩 — 진행 중인 요구사항 flush 하고 새 section 시작
            _flush()
            current_section = text
            current_id = ""
            current_title = ""
            continue

        # 본문 단락 — 안에 요구사항 ID 가 있는지 검사
        m = REQ_ID_RE.search(text)
        if m:
            # 새 요구사항 시작 — 이전 것 flush
            _flush()
            current_id    = m.group("id")
            current_title = text
            buf = [text]
        else:
            # 진행 중인 요구사항 본문 누적
            if current_id:
                buf.append(text)

    # 마지막 요구사항 flush
    _flush()
    return sections


# ══════════════════════════════════════════════════════════════
#  변경된 요구사항 + 매핑되는 체크리스트 섹션 식별
# ══════════════════════════════════════════════════════════════
def changed_sections_to_checklist_ranges(changed_sections) -> set:
    """변경된 상단 목차 set → 매칭되는 체크리스트 No 의 집합.
    (checklist_parser 의 매핑 활용)
    """
    from core.checklist_parser import get_no_ranges_for_sections
    return get_no_ranges_for_sections(changed_sections)
