"""ui_save.py — 분석 결과 저장 헬퍼 (MD/HTML/DOCX).

view.py 의 ResultPanel 메서드(_make_filename, _save_md, _save_html, _save_docx,
_save_all, _show_save_popup, _write_html, _write_docx)를 모듈 함수로 분리한다.

ResultPanel 은 본 모듈을 import 해서 호출만 한다 — 위젯 자기 자신과
현재 sum_md / vuln_md / project_name 스냅샷을 인자로 넘긴다.
"""

import os
import re
import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QPushButton, QVBoxLayout,
)

from config import C
from .ui_md import _md_to_html


# ──────────────────────────────────────────────────────────────
#  공용 안내 다이얼로그 — 저장할 결과물이 없을 때 사용
# ──────────────────────────────────────────────────────────────
def _show_no_result_dialog(parent):
    """다크 테마 일관 스타일의 '저장할 결과물 없음' 안내 다이얼로그."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("저장할 결과물 없음")
    dlg.setFixedSize(400, 260)
    dlg.setStyleSheet(
        f"QDialog {{ background:{C.BG_PANEL}; border:1px solid {C.BDR2}; }}"
    )

    vlay = QVBoxLayout(dlg)
    vlay.setContentsMargins(32, 28, 32, 24)
    vlay.setSpacing(0)

    # 아이콘
    icon_lbl = QLabel("⚠️")
    icon_lbl.setFont(QFont("Segoe UI Emoji", 28))
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_lbl.setStyleSheet("background:transparent; border:none;")
    vlay.addWidget(icon_lbl)
    vlay.addSpacing(10)

    # 타이틀
    title = QLabel("저장할 분석 결과가 없습니다")
    title.setFont(QFont(C.FUI, 14, QFont.Weight.Bold))
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(f"color:{C.T0}; background:transparent; border:none;")
    vlay.addWidget(title)
    vlay.addSpacing(8)

    # 설명
    desc = QLabel("먼저 '🤖 AI 분석 실행' 버튼으로\n분석을 완료해주세요.")
    desc.setFont(QFont(C.FUI, 10))
    desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
    desc.setStyleSheet(f"color:{C.T3}; background:transparent; border:none;")
    vlay.addWidget(desc)
    vlay.addSpacing(22)

    # OK 버튼
    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    ok_btn = QPushButton("확인")
    ok_btn.setFixedSize(110, 38)
    ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    # 프로그램 메인 BLUE 통일
    ok_btn.setStyleSheet(
        f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
        f"  border:none; border-radius:8px;"
        f"  font-size:12px; font-weight:700; }}"
        f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
        f"QPushButton:pressed {{ background:{C.BLUE_DK}; }}")
    ok_btn.clicked.connect(dlg.accept)
    ok_btn.setDefault(True)
    btn_row.addWidget(ok_btn)
    btn_row.addStretch(1)
    vlay.addLayout(btn_row)

    # 부모 창 중앙
    if parent is not None and hasattr(parent, "isVisible") and parent.isVisible():
        win = parent.window() if hasattr(parent, "window") else parent
        geo = win.geometry()
        dlg.move(
            geo.x() + (geo.width()  - dlg.width())  // 2,
            geo.y() + (geo.height() - dlg.height()) // 2,
        )
    dlg.exec()


# ──────────────────────────────────────────────────────────────
#  파일명 헬퍼
# ──────────────────────────────────────────────────────────────
def make_filename(project_name: str, ext: str) -> str:
    """`{프로젝트명}_AIreview_{YYYYMMDD_HHMMSS}.{ext}` 형식."""
    proj = re.sub(r'[\\/:*?"<>|]', '_', project_name) or "Project"
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{proj}_AIreview_{ts}.{ext}"


# ──────────────────────────────────────────────────────────────
#  저장 팝업 메뉴
# ──────────────────────────────────────────────────────────────
def show_save_popup(parent, anchor_btn, sum_md: str, vuln_md: str, project_name: str):
    """저장 형식 선택 팝업을 anchor_btn 아래에 띄운다.
    AI 분석 전(요약/취약점 모두 비어있음) 클릭 시 경고 팝업을 띄우고 메뉴는 표시하지 않는다.
    """
    if not (sum_md.strip() or vuln_md.strip()):
        _show_no_result_dialog(parent)
        return

    menu = QMenu(parent)
    menu.setStyleSheet(f"""
        QMenu {{
            background:{C.BG_CARD}; border:1px solid {C.BDR};
            border-radius:6px; padding:4px 0;
        }}
        QMenu::item {{
            color:{C.T1}; padding:8px 20px;
            font-family:'{C.FUI}'; font-size:11px;
        }}
        QMenu::item:selected {{ background:{C.BG_HOVER}; color:{C.T0}; }}
        QMenu::separator {{ height:1px; background:{C.BDR}; margin:4px 0; }}
    """)
    menu.addAction("📄  MD 저장",
                   lambda: save_md(parent, sum_md, vuln_md, project_name))
    menu.addAction("🌐  HTML 저장",
                   lambda: save_html(parent, sum_md, vuln_md, project_name))
    menu.addAction("📝  DOCX 저장",
                   lambda: save_docx(parent, sum_md, vuln_md, project_name))
    menu.addSeparator()
    menu.addAction("💾  모두 저장",
                   lambda: save_all(parent, sum_md, vuln_md, project_name))
    menu.exec(anchor_btn.mapToGlobal(anchor_btn.rect().bottomLeft()))


# ──────────────────────────────────────────────────────────────
#  개별 형식 저장
# ──────────────────────────────────────────────────────────────
def save_md(parent, sum_md: str, vuln_md: str, project_name: str):
    text = sum_md + "\n\n---\n\n" + vuln_md
    if not text.strip():
        return
    fname = make_filename(project_name, "md")
    path, _ = QFileDialog.getSaveFileName(parent, "MD 저장", fname, "Markdown (*.md)")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def save_html(parent, sum_md: str, vuln_md: str, project_name: str):
    if not (sum_md.strip() or vuln_md.strip()):
        return
    fname = make_filename(project_name, "html")
    path, _ = QFileDialog.getSaveFileName(parent, "HTML 저장", fname, "HTML 파일 (*.html)")
    if not path:
        return
    _write_html(path, sum_md, vuln_md, project_name)


def save_docx(parent, sum_md: str, vuln_md: str, project_name: str):
    if not (sum_md.strip() or vuln_md.strip()):
        return
    fname = make_filename(project_name, "docx")
    path, _ = QFileDialog.getSaveFileName(parent, "DOCX 저장", fname, "Word 문서 (*.docx)")
    if not path:
        return
    _write_docx(parent, path, sum_md, vuln_md, project_name)


def save_all(parent, sum_md: str, vuln_md: str, project_name: str):
    if not (sum_md.strip() or vuln_md.strip()):
        return
    out_dir = QFileDialog.getExistingDirectory(parent, "저장 폴더 선택")
    if not out_dir:
        return
    stem = make_filename(project_name, "")[:-1]   # 확장자 없는 기본 이름
    text = sum_md + "\n\n---\n\n" + vuln_md
    # MD
    with open(os.path.join(out_dir, stem + ".md"), "w", encoding="utf-8") as f:
        f.write(text)
    # HTML
    _write_html(os.path.join(out_dir, stem + ".html"), sum_md, vuln_md, project_name)
    # DOCX
    _write_docx(parent, os.path.join(out_dir, stem + ".docx"), sum_md, vuln_md, project_name)


# ──────────────────────────────────────────────────────────────
#  포맷별 실제 기록 헬퍼
# ──────────────────────────────────────────────────────────────
def _write_html(path: str, sum_md: str, vuln_md: str, project_name: str):
    ts        = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    sum_html  = _md_to_html(sum_md)
    vuln_html = _md_to_html(vuln_md)
    proj      = project_name or "SW 배포 파이프라인"
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{proj} — AI 리뷰 결과</title>
</head>
<body style="margin:0;padding:0;background:#F8FAFC;">
<div style="max-width:960px;margin:0 auto;padding:32px 24px;">
  <h1 style="font-family:Segoe UI,sans-serif;color:#0F172A;font-size:22px;margin-bottom:32px;">
    {proj} — SW 배포 파이프라인 결과
    <span style="font-size:13px;color:#94A3B8;font-weight:normal;margin-left:12px;">{ts}</span>
  </h1>
  <h2 style="font-family:Segoe UI,sans-serif;color:#D97706;font-size:16px;margin-bottom:12px;">
    변경점 요약
  </h2>
  {sum_html}
  <hr style="border:none;border-top:1px solid #E2E8F0;margin:32px 0;">
  <h2 style="font-family:Segoe UI,sans-serif;color:#DC2626;font-size:16px;margin-bottom:12px;">
    취약점 분석
  </h2>
  {vuln_html}
</div>
</body>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def _write_docx(parent, path: str, sum_md: str, vuln_md: str, project_name: str):
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        QMessageBox.warning(parent, "DOCX 저장 실패",
            "python-docx 패키지가 필요합니다.\n\npip install python-docx")
        return

    doc = Document()
    proj = project_name or "SW 배포 파이프라인"
    ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── 페이지 여백 설정 (A4 기준 2cm) ─────────────────────────
    from docx.shared import Cm
    for section in doc.sections:
        section.top_margin    = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.5)

    # ── 기본 폰트 설정 ──────────────────────────────────────────
    from docx.oxml.ns import qn
    style = doc.styles["Normal"]
    style.font.name = "맑은 고딕"
    style.font.size = Pt(10)
    _set_east_asia_font(style.element)

    def _set_heading_style(level, size, color_hex, bold=True):
        """헤딩 스타일 커스터마이즈"""
        try:
            h = doc.styles[f"Heading {level}"]
            h.font.name  = "맑은 고딕"
            h.font.size  = Pt(size)
            h.font.bold  = bold
            h.font.color.rgb = RGBColor.from_string(color_hex)
            _set_east_asia_font(h.element)
            pf = h.paragraph_format
            pf.space_before = Pt(12)
            pf.space_after  = Pt(4)
        except Exception:
            pass

    _set_heading_style(1, 16, "1E40AF")
    _set_heading_style(2, 14, "1E40AF")
    _set_heading_style(3, 12, "1E40AF")
    _set_heading_style(4, 11, "334155")

    # ── 제목 ────────────────────────────────────────────────────
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    title_run = title_p.add_run(f"{proj}  —  SW 배포 파이프라인 결과")
    title_run.font.name  = "맑은 고딕"
    title_run.font.size  = Pt(18)
    title_run.font.bold  = True
    title_run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    _set_east_asia_font(title_run.element)

    # 제목 아래 구분선
    _docx_add_border_bottom(title_p, "BFDBFE", 12)

    ts_p = doc.add_paragraph()
    ts_run = ts_p.add_run(f"생성일시: {ts}")
    ts_run.font.size = Pt(9)
    ts_run.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
    _set_east_asia_font(ts_run.element)
    doc.add_paragraph()

    # ── 변경점 요약 섹션 ────────────────────────────────────────
    h = doc.add_heading("📝  변경점 요약", level=1)
    _docx_color_heading(h, "D97706")
    _md_to_docx(doc, sum_md)

    doc.add_page_break()

    # ── 취약점 분석 섹션 ────────────────────────────────────────
    h = doc.add_heading("🔍  취약점 분석", level=1)
    _docx_color_heading(h, "DC2626")
    _md_to_docx(doc, vuln_md)

    doc.save(path)


def _docx_color_heading(heading_para, color_hex: str):
    """헤딩 단락의 폰트 색상을 덮어쓴다."""
    from docx.shared import RGBColor
    from docx.oxml.ns import qn
    for run in heading_para.runs:
        run.font.color.rgb = RGBColor.from_string(color_hex)
        _set_east_asia_font(run.element)


def _docx_add_border_bottom(paragraph, color_hex: str, size: int = 6):
    """단락 아래에 구분선(border-bottom)을 추가한다."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"),   "single")
    bottom.set(qn("w:sz"),    str(size))
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color_hex)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _set_east_asia_font(xml_element, font_name: str = "맑은 고딕"):
    """xml_element(<w:r> 또는 스타일 element) 의 eastAsia 폰트를 안전하게 설정.
    rPr / rFonts 가 없으면 생성하여 추가한다."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    rPr = xml_element.find(qn("w:rPr"))
    if rPr is None:
        rPr = OxmlElement("w:rPr")
        xml_element.append(rPr)
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:eastAsia"), font_name)




# ──────────────────────────────────────────────────────────────
#  마크다운 → DOCX 렌더러 (헤더/표/코드블록/리스트/인라인서식)
#  ─ ui_md._md_to_html 의 마크다운 파싱 로직을 docx 출력에 맞게 포팅.
#    동일한 prompt 출력을 두 포맷에서 일관되게 렌더하도록 같은 규칙 적용
#    (테이블 셀 줄병합, 언어 힌트별 코드블록 분기 등).
# ──────────────────────────────────────────────────────────────
def _md_to_docx(doc, md_text: str):
    from docx.shared import Pt, RGBColor, Inches
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    if not md_text or not md_text.strip():
        return

    lines = md_text.splitlines()

    # ── 전처리: 여러 줄로 쪼개진 테이블 셀 합치기 (ui_md 와 동일 로직) ──
    def _row_ends(s: str) -> bool:
        return s.endswith("|") and not s.endswith("\\|")

    merged: list[str] = []
    j = 0
    while j < len(lines):
        ln = lines[j]
        s  = ln.strip()
        if (s.startswith("|")
                and not re.match(r"^[\|\s\-:]+$", s)
                and not _row_ends(s)):
            while not _row_ends(s) and j + 1 < len(lines):
                j += 1
                nxt = lines[j].strip()
                if not nxt:
                    j -= 1; break
                s = s + " " + nxt
            ln = s
        merged.append(ln)
        j += 1
    lines = merged

    # ── 본 파싱 루프 ───────────────────────────────────────────
    in_table       = False
    table_rows: list[list[str]] = []
    in_code_block  = False
    code_buf: list[str] = []
    code_lang      = ""

    def flush_table():
        nonlocal in_table, table_rows
        if in_table and table_rows:
            _docx_add_table(doc, table_rows)
        table_rows = []
        in_table   = False

    i = 0
    while i < len(lines):
        line     = lines[i]
        stripped = line.strip()

        # 코드 블록 ──────────────────────────────────────────
        if stripped.startswith("```"):
            if in_code_block:
                _docx_add_code_block(doc, code_buf, code_lang)
                code_buf = []; in_code_block = False
            else:
                flush_table()
                in_code_block = True
                code_lang = stripped[3:].strip().lower()
            i += 1; continue
        if in_code_block:
            code_buf.append(line); i += 1; continue

        # 테이블 ─────────────────────────────────────────────
        if stripped.startswith("|"):
            if re.match(r"^[\|\s\-:]+$", stripped):
                # 헤더 구분선 — 행으로 추가하지 않음
                i += 1; continue
            cells = _docx_split_row(stripped)
            table_rows.append(cells); in_table = True
            i += 1; continue
        else:
            flush_table()

        # 헤더 ───────────────────────────────────────────────
        if   stripped.startswith("#### "):
            doc.add_heading(_strip_md_inline(stripped[5:]), level=4)
        elif stripped.startswith("### "):
            doc.add_heading(_strip_md_inline(stripped[4:]), level=3)
        elif stripped.startswith("## "):
            doc.add_heading(_strip_md_inline(stripped[3:]), level=2)
        elif stripped.startswith("# "):
            doc.add_heading(_strip_md_inline(stripped[2:]), level=1)
        # 수평선 ─────────────────────────────────────────────
        elif re.match(r"^[-*_]{3,}$", stripped):
            p = doc.add_paragraph()
            run = p.add_run("─" * 50)
            run.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
        # 인용 (blockquote) ───────────────────────────────────
        elif stripped.startswith("> ") or stripped == ">":
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent  = Pt(14)
            pf.space_before = Pt(3)
            pf.space_after  = Pt(3)
            pPr = p._p.get_or_add_pPr()
            # 배경: 옅은 amber
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"),   "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"),  "FFFBEB")
            pPr.append(shd)
            # 왼쪽 amber 굵은 줄
            pBdr = OxmlElement("w:pBdr")
            left = OxmlElement("w:left")
            left.set(qn("w:val"),   "single")
            left.set(qn("w:sz"),    "18")
            left.set(qn("w:space"), "6")
            left.set(qn("w:color"), "F59E0B")
            pBdr.append(left)
            pPr.append(pBdr)
            if stripped.startswith("> "):
                _docx_add_inline(p, stripped[2:])
        # 리스트 (불릿) ───────────────────────────────────────
        elif re.match(r"^[-*]\s", stripped):
            p = _docx_paragraph_with_style(doc, "List Bullet")
            _docx_add_inline(p, stripped[2:])
        # 리스트 (번호) ───────────────────────────────────────
        elif re.match(r"^\d+\.\s", stripped):
            p = _docx_paragraph_with_style(doc, "List Number")
            content = re.sub(r"^\d+\.\s", "", stripped)
            _docx_add_inline(p, content)
        # 단독 볼드 줄 → 작은 헤더 (h5 역할) ───────────────────
        elif re.match(r"^\*\*[^*]+\*\*$", stripped):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after  = Pt(2)
            run = p.add_run(stripped[2:-2])
            run.bold = True
            run.font.size = Pt(11)
            run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
        # 빈 줄 — 단락 자체로 처리 (간격은 스타일이 줌)
        elif not stripped:
            pass
        # 일반 단락 ───────────────────────────────────────────
        else:
            p = doc.add_paragraph()
            _docx_add_inline(p, stripped)

        i += 1

    # 미flush 상태 정리
    flush_table()
    if in_code_block and code_buf:
        _docx_add_code_block(doc, code_buf, code_lang)


def _docx_paragraph_with_style(doc, style_name: str):
    """주어진 스타일로 paragraph 생성. 스타일 부재 시 일반 paragraph 로 폴백."""
    try:
        return doc.add_paragraph(style=style_name)
    except KeyError:
        return doc.add_paragraph()


def _strip_md_inline(text: str) -> str:
    """헤딩 안의 `code` / **bold** / *italic* 마커만 제거 — 헤딩은 인라인 서식 미지원."""
    text = re.sub(r"`([^`]+)`",      r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*",    r"\1", text)
    return text


def _docx_split_row(line: str) -> list[str]:
    """마크다운 표 행을 셀 리스트로 분해. \\| (이스케이프) 와 || (논리OR) 보존."""
    s = line.strip().strip("|")
    PH1, PH2 = "\x00", "\x01"
    s = s.replace("\\|", PH1).replace("||", PH2)
    return [c.strip().replace(PH1, "|").replace(PH2, "||") for c in s.split("|")]


def _docx_add_inline(paragraph, text: str):
    """단락에 인라인 서식(**bold** / *italic* / `code`) 적용된 run 들을 추가."""
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    pattern = r"(\*\*[^\*]+\*\*|`[^`]+`|\*[^\*\s][^\*]*\*)"
    parts = re.split(pattern, text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            r = paragraph.add_run(part[2:-2]); r.bold = True
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            r = paragraph.add_run(part[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(0x92, 0x40, 0x0E)
            # 인라인 코드 amber 배경 음영
            rPr = r._r.get_or_add_rPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"),   "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"),  "FEF3C7")
            rPr.append(shd)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            r = paragraph.add_run(part[1:-1]); r.italic = True
        else:
            paragraph.add_run(part)


def _docx_add_table(doc, rows: list[list[str]]):
    """마크다운 표 행들을 실제 Word 표로 추가. 첫 행은 헤더 (bold), 짝수 행 줄무늬."""
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    if not rows:
        return
    n_cols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=n_cols)
    # 'Table Grid' 로 기본 테두리 확보
    for sty in ("Table Grid", "Normal Table"):
        try:
            table.style = sty; break
        except KeyError:
            continue

    # 테이블 전체 테두리 색상 설정 (연한 slate)
    tbl = table._tbl
    tblPr = tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    tblBorders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"),   "single")
        b.set(qn("w:sz"),    "4")
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), "CBD5E1")
        tblBorders.append(b)
    tblPr.append(tblBorders)

    for r_idx, row in enumerate(rows):
        for c_idx in range(n_cols):
            cell = table.cell(r_idx, c_idx)
            text = row[c_idx] if c_idx < len(row) else ""
            cell.text = ""              # 기본 paragraph 비우기
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after  = Pt(1)
            _docx_add_inline(p, text)

            tcPr = cell._tc.get_or_add_tcPr()
            # 셀 내부 여백
            tcMar = OxmlElement("w:tcMar")
            for side, val in [("top","60"),("bottom","60"),("left","108"),("right","108")]:
                m = OxmlElement(f"w:{side}")
                m.set(qn("w:w"),    val)
                m.set(qn("w:type"), "dxa")
                tcMar.append(m)
            tcPr.append(tcMar)

            if r_idx == 0:
                # 헤더 행: bold + 파랑 배경
                for run in p.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0x1E, 0x40, 0xAF)
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"),   "clear")
                shd.set(qn("w:color"), "auto")
                shd.set(qn("w:fill"),  "DBEAFE")
                tcPr.append(shd)
            elif r_idx % 2 == 0:
                # 짝수 데이터 행: 아주 연한 줄무늬
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"),   "clear")
                shd.set(qn("w:color"), "auto")
                shd.set(qn("w:fill"),  "F8FAFC")
                tcPr.append(shd)


def _docx_add_code_block(doc, lines: list[str], lang: str):
    """코드 블록을 모노스페이스 + 음영 단락으로 추가.
    언어 힌트 없는 ``` 는 라이트 슬레이트 콜아웃 (발생 시나리오용),
    ```c 등 언어 있는 블록은 다크 슬레이트 코드 박스 (ui_md 와 동일 분기).
    첫/마지막 줄에 상단/하단 테두리 추가."""
    from docx.shared import Pt, RGBColor, Inches
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    if not lines:
        return

    is_callout   = (lang == "")
    fill_hex     = "F1F5F9" if is_callout else "1E293B"
    text_color   = (RGBColor(0x1E, 0x29, 0x3B) if is_callout
                    else RGBColor(0xE2, 0xE8, 0xF0))
    border_color = "94A3B8" if is_callout else "475569"
    n = len(lines)

    for idx, code_line in enumerate(lines):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_before = Pt(4) if idx == 0     else Pt(0)
        pf.space_after  = Pt(4) if idx == n - 1 else Pt(0)
        pf.left_indent  = Inches(0.2)

        # 단락 배경(음영)
        pPr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"),   "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"),  fill_hex)
        pPr.append(shd)

        # 첫 줄 상단 / 마지막 줄 하단 테두리
        if idx == 0 or idx == n - 1:
            pBdr = OxmlElement("w:pBdr")
            if idx == 0:
                top = OxmlElement("w:top")
                top.set(qn("w:val"),   "single")
                top.set(qn("w:sz"),    "4")
                top.set(qn("w:space"), "1")
                top.set(qn("w:color"), border_color)
                pBdr.append(top)
            if idx == n - 1:
                bottom = OxmlElement("w:bottom")
                bottom.set(qn("w:val"),   "single")
                bottom.set(qn("w:sz"),    "4")
                bottom.set(qn("w:space"), "1")
                bottom.set(qn("w:color"), border_color)
                pBdr.append(bottom)
            pPr.append(pBdr)

        # 빈 줄도 음영 유지를 위해 공백 한 칸 삽입
        run = p.add_run(code_line if code_line else " ")
        run.font.name      = "Consolas"
        run.font.size      = Pt(9.5)
        run.font.color.rgb = text_color

    # 코드블록 끝 여백
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after  = Pt(6)
