# -*- coding: utf-8 -*-
"""_write_docx 원복 + 스타일 개선"""

with open('view/ui_save.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start = next(i for i, l in enumerate(lines) if 'def _write_docx(' in l)
end   = next(i for i in range(start, start+80) if 'doc.save(path)' in lines[i]) + 1

new_block = '''\
def _write_docx(parent, path: str, sum_md: str, vuln_md: str, project_name: str):
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        QMessageBox.warning(parent, "DOCX 저장 실패",
            "python-docx 패키지가 필요합니다.\\n\\npip install python-docx")
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
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")

    def _set_heading_style(level, size, color_hex, bold=True):
        """헤딩 스타일 커스터마이즈"""
        try:
            h = doc.styles[f"Heading {level}"]
            h.font.name  = "맑은 고딕"
            h.font.size  = Pt(size)
            h.font.bold  = bold
            h.font.color.rgb = RGBColor.from_string(color_hex)
            h.element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")
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
    title_run.element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")

    # 제목 아래 구분선
    _docx_add_border_bottom(title_p, "BFDBFE", 12)

    ts_p = doc.add_paragraph()
    ts_run = ts_p.add_run(f"생성일시: {ts}")
    ts_run.font.size = Pt(9)
    ts_run.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
    ts_run.element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")
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
        run.element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")


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

'''.splitlines(keepends=True)

new_lines = lines[:start] + new_block + lines[end:]

with open('view/ui_save.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

with open('_revert_done.txt', 'w') as f:
    f.write(f"OK: replaced lines {start+1}-{end}\n")
