"""ui_md.py — 마크다운 → HTML 변환 헬퍼 (UI/Qt 의존없음).

view.py 에서 분리된 순수 함수 모듈:
  _inline_md             : 인라인 마크다운(bold/em/code/원문자/한글 라벨) 변환
  _esc_html              : HTML 특수문자 이스케이프
  _highlight_code_comments : C/C++ 주석을 초록 span 으로 강조
  _md_to_html            : 마크다운 본문 전체 → 스타일된 HTML 문자열

ResultView(텍스트뷰 렌더), ui_save.py(HTML 저장) 양쪽이 import 한다.
"""

import re


def _inline_md(text: str) -> str:
    """인라인 마크다운(bold, code)을 HTML로 변환."""
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',         text)
    text = re.sub(r'`([^`]+)`',     r'<code>\1</code>',      text)
    # 원문자 ①②③… 앞에 줄바꿈 삽입 (첫 번째 제외) — 테이블 셀 가독성
    text = re.sub(r'(?<=\S)\s*([①②③④⑤⑥⑦⑧⑨⑩])', r'<br>\1', text)
    # 한국어 대괄호 라벨 앞에 줄바꿈 삽입 — `[변수 삭제]`, `[변수 추가]`,
    # `[연산 로직 변경]` 등 다중 항목을 개별 줄로 분리해 가독성 확보.
    # 첫 라벨(셀 맨 앞)은 (?<=\S)\s+ 미충족으로 영향 없음.
    # `[Mandatory]`, `[App_Charger.c]` 같은 영문/혼합 라벨은 한글 시작 조건으로 제외.
    text = re.sub(r'(?<=\S)\s+(\[[가-힣][^\]]*\])', r'<br>\1', text)
    # 코딩 표준 태그 앞에도 줄바꿈 — SA 표의 다중 규칙 가독성 (CERT-C, MISRA-C[:YYYY])
    # 영문 브래킷 일반 매칭은 `[App_Charger.c]` 같은 파일 라벨까지 건드리므로
    # 표준 태그만 화이트리스트로 제한.
    text = re.sub(r'(?<=\S)\s+(\[(?:CERT-C|MISRA-C(?::\d{4})?)\])', r'<br>\1', text)
    return text


# 코드블록 주석 강조용 색상 (VS Code 다크 테마 그린)
_COMMENT_GREEN = "#6A9955"


def _esc_html(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _highlight_code_comments(lines: list[str]) -> list[str]:
    """C/C++ 스타일 주석( // … , /* … */ )을 초록색 span으로 감싼다.
    멀티라인 /* */ 블록도 라인 경계를 넘어 추적한다."""
    out: list[str] = []
    in_block = False
    for line in lines:
        parts: list[str] = []
        i, n = 0, len(line)
        while i < n:
            if in_block:
                end = line.find('*/', i)
                if end == -1:
                    parts.append(f'<span style="color:{_COMMENT_GREEN}">{_esc_html(line[i:])}</span>')
                    i = n
                else:
                    parts.append(f'<span style="color:{_COMMENT_GREEN}">{_esc_html(line[i:end+2])}</span>')
                    i = end + 2
                    in_block = False
            else:
                ss = line.find('//', i)
                sb = line.find('/*', i)
                cands = [x for x in (ss, sb) if x != -1]
                if not cands:
                    parts.append(_esc_html(line[i:]))
                    i = n
                else:
                    nxt = min(cands)
                    if nxt > i:
                        parts.append(_esc_html(line[i:nxt]))
                    if nxt == ss:
                        parts.append(f'<span style="color:{_COMMENT_GREEN}">{_esc_html(line[nxt:])}</span>')
                        i = n
                    else:
                        end = line.find('*/', nxt + 2)
                        if end == -1:
                            parts.append(f'<span style="color:{_COMMENT_GREEN}">{_esc_html(line[nxt:])}</span>')
                            i = n
                            in_block = True
                        else:
                            parts.append(f'<span style="color:{_COMMENT_GREEN}">{_esc_html(line[nxt:end+2])}</span>')
                            i = end + 2
        out.append(''.join(parts))
    return out


def _md_to_html(text: str) -> str:
    """마크다운 텍스트를 스타일된 HTML로 변환한다."""
    CSS = """<style>
* { box-sizing:border-box; }
body { font-family:'Segoe UI'; font-size:13px; color:#1E293B;
       margin:16px 20px; line-height:1.8; }
h2 { color:#1E40AF; font-size:16px; font-weight:700;
     border-bottom:2px solid #BFDBFE; padding:6px 0 5px; margin:18px 0 10px; }
h3 { color:#1E40AF; font-size:14px; font-weight:700;
     border-left:4px solid #3B82F6; padding:4px 0 4px 10px;
     margin:20px 0 10px; background:#FFFFFF; }
h4 { color:#1E293B; font-size:14px; font-weight:700;
     border-left:3px solid #93C5FD; padding:4px 0 4px 10px;
     margin:14px 0 6px; background:#EFF6FF; }
h5 { color:#1E293B; font-size:14px; font-weight:700;
     border-bottom:2px solid #BFDBFE; padding:6px 0 4px;
     margin:20px 0 8px; background:#FFFFFF; }
table { border-collapse:collapse; width:100%; margin:6px 0 12px; font-size:12px;
        table-layout:fixed; }
th { background:#EFF6FF; color:#1D4ED8; padding:7px 10px;
     border:1px solid #BFDBFE; text-align:left; font-weight:600;
     white-space:nowrap; width:90px; }
td { padding:8px 10px; border:1px solid #E2E8F0; vertical-align:top;
     word-break:keep-all; overflow-wrap:anywhere; line-height:1.75; }
tr:nth-child(even) td { background:#F8FAFC; }
td ol, td ul { margin:2px 0; padding-left:16px; }
td li { margin:5px 0; line-height:1.75; }
code { background:#FDE68A; color:#78350F; padding:2px 6px;
       border-radius:3px; font-family:Consolas; font-size:12px;
       font-weight:600; }
/* 표 셀 안의 인라인 코드는 톤 다운 — 노란 펠릿이 셀마다 5~6개씩 박혀
   가독성을 해치므로 옅은 슬레이트 + 작은 패딩으로 시각 노이즈 축소 */
td code { background:#F1F5F9; color:#334155; padding:1px 4px;
          border:1px solid #E2E8F0; border-radius:3px;
          font-family:Consolas; font-size:11px; font-weight:600; }
pre  { background:#1E293B; color:#E2E8F0; border:none; border-radius:8px;
       padding:14px 16px; font-family:Consolas; font-size:12px;
       margin:10px 0 14px; white-space:pre-wrap; }
hr  { border:none; border-top:1px solid #E2E8F0; margin:18px 0; }
ul  { padding-left:20px; margin:4px 0 8px; }
ol  { padding-left:20px; margin:4px 0 8px; }
li  { margin:5px 0; background:#FFFFFF; }
p   { margin:3px 0 7px; background:#FFFFFF; }

</style>"""

    lines = text.splitlines()

    # ── 전처리: 여러 줄로 쪼개진 테이블 셀 합치기 ─────────────
    # 예) C 코드 백슬래시 줄연속 등으로 | 로 시작했지만 | 로 끝나지 않는 행
    # \| (이스케이프된 파이프) 는 행 종료 판단에서 제외
    def _row_ends(s: str) -> bool:
        """실제 | 로 끝나는지 판단 (\\| 이스케이프는 무시)."""
        return s.endswith('|') and not s.endswith('\\|')

    merged: list[str] = []
    j = 0
    while j < len(lines):
        ln = lines[j]
        s  = ln.strip()
        if (s.startswith('|')
                and not re.match(r'^[\|\s\-:]+$', s)   # 구분선 제외
                and not _row_ends(s)):                  # 아직 닫히지 않은 행
            while not _row_ends(s) and j + 1 < len(lines):
                j += 1
                nxt = lines[j].strip()
                if not nxt:          # 빈 줄 → 합치기 중단
                    j -= 1; break
                s = s + ' ' + nxt
            ln = s
        merged.append(ln)
        j += 1
    lines = merged

    out   = [CSS]
    i     = 0
    in_table        = False
    table_hdr_done  = False
    in_list         = False
    list_tag        = 'ul'
    in_code_block   = False
    code_lang       = ''   # 코드 펜스 언어 힌트 ("" = 시나리오/콜아웃, "c"/"cpp" = 코드)
    code_buf: list  = []
    # 직전 출력이 </pre> 였는지 추적 — 연속 pre 블록 병합용
    last_was_pre    = False
    in_blockquote   = False   # 연속된 '>' 줄을 하나의 <blockquote> 로 묶기

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append(f'</{list_tag}>'); in_list = False

    def flush_table():
        nonlocal in_table, table_hdr_done
        if in_table:
            out.append('</table>'); in_table = False; table_hdr_done = False

    def flush_blockquote():
        nonlocal in_blockquote
        if in_blockquote:
            out.append('</blockquote>'); in_blockquote = False

    while i < len(lines):
        line     = lines[i]
        stripped = line.strip()

        # ── 코드 블록 ──────────────────────────────────────────
        if stripped.startswith('```'):
            if in_code_block:
                # 언어 힌트 없는 펜스(```)는 "발생 시나리오" 등 콜아웃으로 렌더 →
                # 라이트 앰버 배경 + 좌측 보더로 코드 블록과 구분.
                if code_lang == '':
                    body = '<br>'.join(_esc_html(s) for s in code_buf)
                    out.append(
                        '<pre style="background:#E2E8F0;color:#1E293B;'
                        'border:1px solid #CBD5E1;border-left:4px solid #64748B;'
                        'border-radius:6px;padding:12px 16px;margin:12px 0 18px;'
                        'font-family:Consolas,monospace;font-size:12px;'
                        'line-height:1.7;">' + body + '</pre>'
                    )
                else:
                    # pre 태그를 닫을 때 배경색 지정 → QTextEdit 상속 방지
                    # 주석( // , /* */ )은 초록색으로 강조
                    escaped = _highlight_code_comments(code_buf)
                    out.append(
                        '<pre style="background:#1E293B;color:#E2E8F0;'
                        'border-radius:8px;padding:14px 18px;margin:12px 0 18px;'
                        'font-family:Consolas,monospace;font-size:12px;line-height:1.65;">'
                        + '<br>'.join(escaped) + '</pre>'
                    )
                out.append('<p style="margin:0;padding:0;background:#FFFFFF;'
                           'font-size:1px;line-height:2px;"> </p>')
                code_buf.clear(); in_code_block = False; code_lang = ''
                last_was_pre = True
            else:
                flush_list(); flush_table()
                code_lang = stripped[3:].strip().lower()
                in_code_block = True
                last_was_pre  = False
            i += 1; continue
        if in_code_block:
            code_buf.append(line); i += 1; continue

        # ── HTML 블록 통과 (table 등) ─────────────────────────
        # CB 위키 마크다운 렌더러가 마크다운 표 separator 를 텍스트로 출력하는
        # 버그 회피용 — 본문에 직접 <table> 을 임베드하면 양쪽 모드 모두 정상 렌더.
        if re.match(r'^<table\b', stripped, re.IGNORECASE):
            flush_list(); flush_table()
            # </table> 까지 그대로 방출
            while i < len(lines):
                out.append(lines[i])
                if re.search(r'</table\s*>', lines[i], re.IGNORECASE):
                    break
                i += 1
            i += 1; last_was_pre = False; continue

        # ── 테이블 ─────────────────────────────────────────────
        if stripped.startswith('|'):
            flush_list()
            if not in_table:
                out.append('<table>'); in_table = True; table_hdr_done = False
            if re.match(r'^[\|\s\-:]+$', stripped):
                table_hdr_done = True; i += 1; continue
            # \| (이스케이프된 파이프) 와 || (C 논리 OR) 을 구분자로 취급하지 않음
            _PH = '\x00'   # NULL 문자를 임시 플레이스홀더로 사용
            _raw = stripped.strip('|').replace('\\|', _PH)
            # || 도 하나의 논리 연산자로 보존 (→ _PH2 로 치환 후 복원)
            _PH2 = '\x01'
            _raw = _raw.replace('||', _PH2)
            cells = [c.strip().replace(_PH, '|').replace(_PH2, '||')
                     for c in _raw.split('|')]
            tag   = 'td' if table_hdr_done else 'th'
            out.append('<tr>' + ''.join(f'<{tag}>{_inline_md(c)}</{tag}>' for c in cells) + '</tr>')
            i += 1; last_was_pre = False; continue
        else:
            flush_table()

        # ── 헤더 ───────────────────────────────────────────────
        if   stripped.startswith('#### '):
            flush_list(); flush_blockquote(); out.append(f'<h4>{_inline_md(stripped[5:])}</h4>'); last_was_pre = False
        elif stripped.startswith('### '):
            flush_list(); flush_blockquote(); out.append(f'<h3>{_inline_md(stripped[4:])}</h3>'); last_was_pre = False
        elif stripped.startswith('## '):
            flush_list(); flush_blockquote(); out.append(f'<h2>{_inline_md(stripped[3:])}</h2>'); last_was_pre = False
        elif stripped.startswith('# '):
            flush_list(); flush_blockquote(); out.append(f'<h1>{_inline_md(stripped[2:])}</h1>'); last_was_pre = False
        # ── 구분선 ─────────────────────────────────────────────
        elif re.match(r'^[-*_]{3,}$', stripped):
            flush_list(); flush_blockquote(); out.append('<hr>'); last_was_pre = False
        # ── blockquote ────────────────────────────────────────
        # '>' 로 시작하는 줄들을 하나의 <blockquote> 로 묶음 — 결론/추론/주석 강조.
        # _normalize_user_text 가 '->' / '→' 를 '> →' 로 치환한 결과도 여기서 처리됨.
        elif stripped.startswith('>'):
            flush_list(); flush_table()
            bq_content = stripped[1:].lstrip()
            if not in_blockquote:
                out.append('<blockquote>')
                in_blockquote = True
                out.append(_inline_md(bq_content))
            else:
                out.append('<br>' + _inline_md(bq_content))
            last_was_pre = False
        # ── 리스트 ─────────────────────────────────────────────
        elif re.match(r'^[-*]\s', stripped):
            flush_blockquote()
            if not in_list or list_tag != 'ul':
                flush_list(); out.append('<ul>'); in_list = True; list_tag = 'ul'
            out.append(f'<li>{_inline_md(stripped[2:])}</li>'); last_was_pre = False
        elif re.match(r'^\d+\.\s', stripped):
            flush_blockquote()
            if not in_list or list_tag != 'ol':
                flush_list(); out.append('<ol>'); in_list = True; list_tag = 'ol'
            ol_content = re.sub(r'^\d+\.\s', '', stripped)
            out.append(f'<li>{_inline_md(ol_content)}</li>'); last_was_pre = False
        # ── 빈 줄 ──────────────────────────────────────────────
        elif stripped == '':
            flush_list(); flush_blockquote()
            # pre 블록 직후 빈줄은 완전 무시 → 검은배경 사이 흰줄 방지
            if not last_was_pre:
                out.append('<p style="margin:3px 0;background:#FFFFFF;"></p>')
        # ── 단독 볼드 줄 → 섹션 헤더 (h5) ─────────────────────
        elif re.match(r'^\*\*[^*]+\*\*$', stripped):
            flush_list(); flush_blockquote()
            content = stripped[2:-2]
            out.append(f'<h5>{_inline_md(content)}</h5>'); last_was_pre = False
        # ── 일반 텍스트 ────────────────────────────────────────
        else:
            flush_list(); flush_blockquote()
            out.append(f'<p style="color:#1E293B;background:#FFFFFF;margin:4px 0 8px;">{_inline_md(stripped)}</p>')
            last_was_pre = False

        i += 1

    flush_list(); flush_table(); flush_blockquote()
    return '\n'.join(out)


# ──────────────────────────────────────────────────────────────
#  _inline_styles_for_cb — <style> 블록을 인라인 style 속성으로 변환
# ──────────────────────────────────────────────────────────────
def _inline_styles_for_cb(html: str) -> str:
    """`_md_to_html` 출력의 <style> 블록을 각 태그의 인라인 style 속성으로
    옮긴다. Codebeamer 등 sanitizer 가 <style> 태그를 제거하는 환경에서도
    표/헤더 시각 요소가 유지되도록 한다.

    적용 대상: 클래스/속성 없는 평탄 태그(table/th/td/h2~h5/code/ul/ol/li/hr).
    이미 style 속성이 있는 태그(<pre style=...>, <p style=...>) 는 건드리지 않음.
    """
    # 1) <style>...</style> 블록 자체는 제거
    html = re.sub(r'<style[^>]*>.*?</style>', '',
                  html, flags=re.DOTALL | re.IGNORECASE)

    # 2) 태그별 인라인 스타일 매핑 (CSS 와 동일 시각 — 일부 단순화)
    inline_styles = {
        'table': ('border-collapse:collapse;width:100%;'
                  'margin:6px 0 12px;font-size:12px;'),
        'th':    ('background:#EFF6FF;color:#1D4ED8;padding:7px 10px;'
                  'border:1px solid #BFDBFE;text-align:left;'
                  'font-weight:600;'),
        'td':    ('padding:8px 10px;border:1px solid #E2E8F0;'
                  'vertical-align:top;line-height:1.6;'),
        'h1':    ('color:#1E3A8A;font-size:18px;font-weight:700;'
                  'border-bottom:2px solid #1E40AF;'
                  'padding:8px 0 6px;margin:20px 0 12px;'),
        'h2':    ('color:#1E40AF;font-size:16px;font-weight:700;'
                  'border-bottom:2px solid #BFDBFE;'
                  'padding:6px 0 5px;margin:18px 0 10px;'),
        'h3':    ('color:#1E40AF;font-size:14px;font-weight:700;'
                  'border-left:4px solid #3B82F6;'
                  'padding:4px 0 4px 10px;margin:20px 0 10px;'),
        'h4':    ('color:#1E293B;font-size:14px;font-weight:700;'
                  'border-left:3px solid #93C5FD;'
                  'padding:4px 0 4px 10px;margin:14px 0 6px;'
                  'background:#EFF6FF;'),
        'h5':    ('color:#1E293B;font-size:14px;font-weight:700;'
                  'border-bottom:2px solid #BFDBFE;'
                  'padding:6px 0 4px;margin:20px 0 8px;'),
        'code':  ('background:#FDE68A;color:#78350F;padding:2px 6px;'
                  'border-radius:3px;font-family:Consolas,monospace;'
                  'font-size:12px;font-weight:600;'),
        'hr':    ('border:none;border-top:1px solid #E2E8F0;margin:18px 0;'),
        'ul':    ('padding-left:22px;margin:6px 0 10px;line-height:1.7;'),
        'ol':    ('padding-left:22px;margin:6px 0 10px;line-height:1.7;'),
        'li':    ('margin:6px 0;color:#1E293B;'),
        # blockquote — 결론/추론(→ 화살표) 강조용. 섹션 라벨(파랑)과 구분되게
        # 연한 슬레이트 톤 + 얇은 회색 좌측 보더. 시각적으로 절제된 인용박스.
        'blockquote': ('border-left:2px solid #94A3B8;background:#F8FAFC;'
                       'color:#475569;padding:6px 12px;margin:6px 0 10px;'
                       'border-radius:0;font-size:12px;line-height:1.6;'),
    }

    # 3) 여는 태그(<tag>) 를 <tag style="..."> 로 치환 — 속성 없는 경우만
    for tag, style in inline_styles.items():
        # <tag>  →  <tag style="...">  (대소문자 무관, 이미 속성 있는 경우 제외)
        html = re.sub(
            rf'<{tag}>',
            f'<{tag} style="{style}">',
            html, flags=re.IGNORECASE)
    return html
