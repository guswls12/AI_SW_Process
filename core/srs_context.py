"""srs_context.py — SRS 변경 검증용 AI 입력 컨텍스트 생성기.

수정 전/후 SRS 전체 텍스트를 그대로 AI 에 보내는 대신:
  1) 문서 전체 목차 (수정 후 기준 섹션 헤더 추출)
  2) 변경된 절의 수정 전·후 풀텍스트 (해당 절만)
  3) 변경 라인 Unified DIFF

이렇게 3-부 구성으로 압축해 토큰 효율을 높이면서도 AI 가
"어디서 어떻게 변경됐는지" 를 충분히 파악할 수 있게 한다.

UI/Qt 의존 없음 — 순수 텍스트 처리.
"""

import re
from difflib import SequenceMatcher


# ══════════════════════════════════════════════════════════════
#  섹션 헤더 패턴
# ══════════════════════════════════════════════════════════════
# 한국어 SRS 에서 흔히 쓰이는 헤더 형식들:
#   "1.2.3 제목" / "1.2.3. 제목"       → 일반 절
#   "표 4-5 ...", "Table 5.1 ..."       → 표 캡션
#   "그림 4-5 ...", "Figure 5.1 ..."    → 그림 캡션
_HEAD_NUMBERED = re.compile(
    r'^\s*(\d+(?:\.\d+){0,4})\.?\s+(\S.*?)\s*$')
_HEAD_TABLE = re.compile(
    r'^\s*(표|Table)\s*(\d+(?:[-.]\d+)?)\s*[:.]?\s*(.*)\s*$',
    re.IGNORECASE)
_HEAD_FIGURE = re.compile(
    r'^\s*(그림|Figure|Fig\.?)\s*(\d+(?:[-.]\d+)?)\s*[:.]?\s*(.*)\s*$',
    re.IGNORECASE)

# 헤더 후보 라인 최대 길이 — 너무 긴 줄은 본문으로 간주
_MAX_HEAD_LEN = 100


def _classify_heading(line: str):
    """라인을 헤더로 분류. 반환: (is_heading, level, display_text).

    level 규칙:
      - "1." → 1, "1.2." → 2, "1.2.3" → 3 ...
      - 표/그림 캡션 → 5 (sub-section 으로 취급)
    """
    s = line.strip()
    if not s or len(s) > _MAX_HEAD_LEN:
        return False, 0, ""

    m = _HEAD_NUMBERED.match(s)
    if m:
        num = m.group(1); title = m.group(2)
        # 너무 일반적인 숫자만 있는 줄 ("1)", "2." 단독 등) 은 제외
        if not title or len(title) < 2:
            return False, 0, ""
        # 제목이 숫자/특수문자로만 끝나면 본문 (예: "1.2 1.5MB")
        if re.fullmatch(r'[\d\s.\-_/]+', title):
            return False, 0, ""
        level = num.count('.') + 1
        return True, level, f"{num} {title}"

    m = _HEAD_TABLE.match(s)
    if m:
        return True, 5, s

    m = _HEAD_FIGURE.match(s)
    if m:
        return True, 5, s

    return False, 0, ""


# ══════════════════════════════════════════════════════════════
#  섹션 파싱
# ══════════════════════════════════════════════════════════════
def parse_sections(lines: list) -> list:
    """텍스트를 섹션 단위로 분할.

    반환: [{level, heading, start, end, body_lines}, ...]
      - level     : 1~5 (1=top, 5=table/figure)
      - heading   : 표시용 헤더 텍스트
      - start/end : 본 섹션 라인 인덱스 (0-based, inclusive)
      - body_lines: 헤더 다음 ~ 다음 헤더 직전까지의 본문 라인 리스트

    첫 헤더 이전의 라인들은 가상의 'preamble' 섹션 (level=0) 으로 묶음.
    """
    sections: list = []
    current = {
        'level':      0,
        'heading':    "(머리말)",
        'start':      0,
        'end':        0,
        'body_lines': [],
    }
    for i, line in enumerate(lines):
        is_h, level, disp = _classify_heading(line)
        if is_h:
            if current is not None:
                current['end'] = i - 1 if i > 0 else 0
                # preamble 이 비어있으면 추가 안 함
                if not (current['level'] == 0
                        and not any(l.strip() for l in current['body_lines'])):
                    sections.append(current)
            current = {
                'level':      level,
                'heading':    disp,
                'start':      i,
                'end':        i,
                'body_lines': [],
            }
        else:
            current['body_lines'].append(line)
    if current is not None:
        current['end'] = max(len(lines) - 1, 0)
        if not (current['level'] == 0
                and not any(l.strip() for l in current['body_lines'])):
            sections.append(current)
    return sections


# ══════════════════════════════════════════════════════════════
#  목차 추출
# ══════════════════════════════════════════════════════════════
def extract_outline(sections: list, max_level: int = 4,
                    max_lines: int = 80) -> str:
    """섹션 목록 → 들여쓰기 목차.

    너무 깊거나 항목 수가 많으면 잘라서 가독성 확보.
    """
    out = []
    n = 0
    for sec in sections:
        lv = sec.get('level', 0)
        if lv == 0 or lv > max_level:
            continue
        indent = '  ' * (lv - 1)
        out.append(f"{indent}{sec['heading']}")
        n += 1
        if n >= max_lines:
            out.append(f"... (이하 {len(sections) - n}개 섹션 생략)")
            break
    return '\n'.join(out)


# ══════════════════════════════════════════════════════════════
#  변경 섹션 식별
# ══════════════════════════════════════════════════════════════
def find_changed_section_keys(before_sections: list, after_sections: list,
                              before_lines: list, after_lines: list) -> set:
    """변경된 라인이 속한 섹션의 heading 집합 반환 (before/after 통합)."""
    matcher = SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    changed_before = set()
    changed_after  = set()
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == 'equal':
            continue
        for i in range(a0, a1):
            changed_before.add(i)
        for i in range(b0, b1):
            changed_after.add(i)

    keys = set()
    for sec in after_sections:
        if any(sec['start'] <= ln <= sec['end'] for ln in changed_after):
            keys.add(sec['heading'])
    for sec in before_sections:
        if any(sec['start'] <= ln <= sec['end'] for ln in changed_before):
            keys.add(sec['heading'])
    return keys


# ══════════════════════════════════════════════════════════════
#  Unified DIFF 생성
# ══════════════════════════════════════════════════════════════
def build_unified_diff(before_lines: list, after_lines: list,
                       context: int = 5) -> str:
    """변경 라인 + 양옆 context 줄 의 unified diff 생성."""
    from difflib import unified_diff
    return "\n".join(unified_diff(
        before_lines, after_lines,
        fromfile="수정전 SRS", tofile="수정후 SRS",
        n=context, lineterm=""))


# ══════════════════════════════════════════════════════════════
#  메인 — 변경 검증용 컨텍스트 빌드
# ══════════════════════════════════════════════════════════════
def build_srs_review_context(before_text: str, after_text: str,
                             max_section_chars: int = 4000,
                             max_total_chars: int = 80000) -> str:
    """SRS 변경 검증 AI 입력용 압축 컨텍스트 생성.

    구성:
      1) 수정 후 SRS 전체 목차 (max_level=4)
      2) 변경된 절의 수정 전·후 풀텍스트 (각 절 max_section_chars 캡)
      3) 변경 라인 Unified DIFF (±5줄 컨텍스트)

    max_total_chars 초과 시 (3) DIFF 부터 잘라냄.

    입력이 둘 다 비어있으면 빈 문자열 반환.
    """
    before_text = before_text or ""
    after_text  = after_text  or ""
    if not before_text.strip() and not after_text.strip():
        return ""

    before_lines = before_text.split('\n')
    after_lines  = after_text.split('\n')

    # 둘 다 짧으면 그냥 전체 텍스트가 더 직관적
    SHORT_THRESHOLD = 2000   # chars per side
    if (len(before_text) <= SHORT_THRESHOLD and
            len(after_text) <= SHORT_THRESHOLD):
        return ("=== 수정 전 SRS (전체) ===\n"
                f"{before_text or '(비어있음)'}\n\n"
                "=== 수정 후 SRS (전체) ===\n"
                f"{after_text or '(비어있음)'}")

    before_secs = parse_sections(before_lines)
    after_secs  = parse_sections(after_lines)

    outline = extract_outline(after_secs)
    changed_keys = find_changed_section_keys(
        before_secs, after_secs, before_lines, after_lines)

    parts: list = []

    # ── 1) 목차 ─────────────────────────────────────────────
    parts.append("=== 수정 후 SRS 전체 목차 (섹션 헤더 추출) ===")
    parts.append(outline if outline.strip() else "(섹션 헤더 인식 실패 — 평문 SRS 일 수 있음)")
    parts.append("")

    # ── 2) 변경된 절의 풀텍스트 (before / after 쌍) ────────
    parts.append("=== 변경된 절 (수정 전·후 풀텍스트) ===")
    if not changed_keys:
        parts.append("(변경된 절을 헤더로 식별 못 함 — DIFF 만 참조)")
    else:
        # 정렬 — after 기준으로 등장 순서
        after_by_head = {s['heading']: s for s in after_secs}
        before_by_head = {s['heading']: s for s in before_secs}
        for sec in after_secs:
            if sec['heading'] not in changed_keys:
                continue
            heading = sec['heading']
            parts.append(f"\n┌─── {heading} ───")
            # [수정 전]
            parts.append("│ [수정 전]")
            b = before_by_head.get(heading)
            if b is None:
                parts.append("│ (수정 전에는 이 절이 없음 — 신규 추가된 절)")
            else:
                body = '\n'.join(b['body_lines']).strip()
                if len(body) > max_section_chars:
                    body = body[:max_section_chars] + "\n... (이하 생략)"
                if body:
                    parts.append(body)
                else:
                    parts.append("(빈 절)")
            # [수정 후]
            parts.append("│ [수정 후]")
            body = '\n'.join(sec['body_lines']).strip()
            if len(body) > max_section_chars:
                body = body[:max_section_chars] + "\n... (이하 생략)"
            if body:
                parts.append(body)
            else:
                parts.append("(빈 절)")
            parts.append("└─────")
        # before 에만 있는 (삭제된) 절도 별도 표시
        for sec in before_secs:
            if (sec['heading'] in changed_keys
                    and sec['heading'] not in after_by_head):
                parts.append(f"\n┌─── {sec['heading']} (삭제됨) ───")
                body = '\n'.join(sec['body_lines']).strip()
                if len(body) > max_section_chars:
                    body = body[:max_section_chars] + "\n... (이하 생략)"
                parts.append(body or "(빈 절)")
                parts.append("└─────")
    parts.append("")

    # ── 3) Unified DIFF ─────────────────────────────────────
    parts.append("=== 변경 라인 Unified DIFF (±5줄 컨텍스트) ===")
    udiff = build_unified_diff(before_lines, after_lines, context=5)
    parts.append(udiff or "(차이 없음)")

    result = "\n".join(parts)

    # 토큰 폭탄 방지 — 너무 길면 DIFF 끝부터 잘라냄
    if len(result) > max_total_chars:
        # 안전 컷 — 잘림 표시 추가
        result = (result[:max_total_chars]
                  + "\n\n... (이하 컨텍스트가 너무 길어 생략됨)")

    return result
