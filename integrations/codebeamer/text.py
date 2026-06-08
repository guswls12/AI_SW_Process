"""text.py — Codebeamer 설명 필드의 HTML/위키마크업 정제.

Qt / requests 의존 없음 — 순수 문자열 처리.
"""

import re


# ══════════════════════════════════════════════════════════════
#  HTML / 위키마크업 정제
# ══════════════════════════════════════════════════════════════
def _clean_text(text: str) -> str:
    """Codebeamer 설명 필드의 HTML/CSS/위키마크업을 제거하고 순수 텍스트를 반환."""
    if not text:
        return ""

    # ── 1. <style> / <script> 블록 제거 ──────────────────────
    text = re.sub(r'<style[^>]*>.*?</style>', '', text,
                  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text,
                  flags=re.DOTALL | re.IGNORECASE)

    # ── 2. Codebeamer 위키 블록 [{...}] 처리 ─────────────────
    # [{Table ...}] 블록: 내부 텍스트(셀 내용)는 보존하고 마크업만 제거
    # 테이블 헤더 구분자(||) → 공백, 셀 구분자(|) → 공백
    def _extract_table_text(m):
        inner = m.group(1)
        # 행 헤더(||...||) 및 셀(|...|) 구분자를 공백으로 치환
        inner = re.sub(r'\|\|', ' ', inner)
        inner = re.sub(r'\|', ' ', inner)
        # [{Table 헤더 줄 제거
        inner = re.sub(r'^\s*Table[^\n]*\n?', '', inner, flags=re.IGNORECASE)
        return inner.strip()

    # [{Table ... }] 블록 → 내부 텍스트 추출
    text = re.sub(r'\[\{(Table[\s\S]*?)\}\]', _extract_table_text, text,
                  flags=re.DOTALL | re.IGNORECASE)

    # [{Image ...}], [{Excerpt ...}] 등 나머지 비텍스트 블록 제거
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'\[\{(?!Table)[^\[\]]*?\}\]', '', text, flags=re.DOTALL | re.IGNORECASE)
    # 닫히지 않은 [{Image... / [{Excerpt... 블록을 '줄 단위'로 제거
    # (Codebeamer 원본이 손상되어 }] 없이 한 줄로 걸쳐 있을 때 대응)
    text = re.sub(
        r'(?m)^\s*\[\{(?:Image|Excerpt|HTML|Tab|Code|Plugin|IFrame)\b[^\n]*\n?',
        '', text, flags=re.IGNORECASE)
    # 잔여 [{...로 시작해서 닫히지 않은 비테이블 블록 제거 (문자열 끝까지)
    text = re.sub(r'\[\{(?!Table)(?:(?!\[\{).)*$', '', text, flags=re.DOTALL | re.IGNORECASE)

    # ── 3. HTML 테이블 구조 → 텍스트 변환 (태그 제거 전에 먼저 처리) ───
    # <th> / <td> 내용 추출 후 " | " 구분
    text = re.sub(r'<t[dh][^>]*>([\s\S]*?)</t[dh]>',
                  lambda m: m.group(1).strip() + ' | ',
                  text, flags=re.DOTALL | re.IGNORECASE)
    # <tr> → 줄바꿈
    text = re.sub(r'</?tr[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?t(?:able|body|head|foot)[^>]*>', '\n', text, flags=re.IGNORECASE)

    # ── 4. HTML 태그 제거 ─────────────────────────────────────
    text = re.sub(r'<[^>]+>', ' ', text)

    # ── 4. Codebeamer 인라인 위키 마크업 제거 ─────────────────
    # 위키 테이블 셀 인라인 CSS 스타일 제거: (border:...; color:...; ...) 패턴
    # 길이 제한 없이 제거하고, 닫히지 않은 ( 도 처리
    text = re.sub(
        r'\([^)]*?(?:border|background|padding|margin|font-|color:|width:|height:|text-align)[^)]*?\)',
        '', text, flags=re.DOTALL)
    # 혹시 남은 스트레이 ) 제거
    # (1) 줄이 ) 하나로만 이루어진 경우 (줄 통째 삭제)
    text = re.sub(r'(?m)^\s*\)\s*$\n?', '', text)
    # (2) 줄 시작부에 ) 가 붙어있는 경우 (뒤에 텍스트가 있어도) — ') 문제점 개선' 같은 패턴
    text = re.sub(r'(?m)^\s*\)+\s*', '', text)
    # {color:#xxx}..{color} 스타일
    text = re.sub(r'\{color[^}]*\}', '', text)
    # [USER:이름] / [LINK:...] 등 대괄호 마크업
    text = re.sub(r'\[/?[A-Z_]+:[^\]]*\]', '', text)
    # 아이콘 단축키: (/) (x) (!) (i) (*) 등
    text = re.sub(r'\([/xX!i\*\+\-\?]\)', '', text)
    # Codebeamer 위키 이스케이프 문자 ~ 제거 (예: Lin~_Slave.c → Lin_Slave.c)
    text = re.sub(r'~(?=[_\[\]\{\}\|\*\^\\])', '', text)
    # ~ (취소선 마커) 나 __ (밑줄 마커) 단독
    text = re.sub(r'(?<!\w)[~_]{2}(?!\w)', '', text)
    # 테이블 셀 구분자 || 및 줄 내 | 제거
    text = re.sub(r'\|\|', ' ', text)
    text = re.sub(r'^\s*\|+', '', text, flags=re.MULTILINE)

    # ── 5. HTML 엔티티 치환 ───────────────────────────────────
    text = (text.replace('&amp;', '&')
                .replace('&lt;', '<')
                .replace('&gt;', '>')
                .replace('&nbsp;', ' ')
                .replace('&quot;', '"')
                .replace('&#39;', "'"))

    # ── 6. 연속 공백/개행 정리 ───────────────────────────────
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
