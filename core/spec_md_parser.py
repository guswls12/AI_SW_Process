"""spec_md_parser.py — ① 사양 변경 페이지 마크다운 역파싱.

CB 트래커에 등록된 이슈의 description 마크다운을 파싱해 폼 입력값
(제목 / JIRA / 본문 / 발생시점 / 수평전개 표) 으로 복원한다.

파싱 대상 마크다운은 view.pages.page_spec 의 다음 메서드로 생성된 것:
  - render_change_item_md   →  "# 📝 이슈" 시작 (이슈 탭)
  - render_spec_change_md   →  "# 📐 사양변경" 시작 (사양변경 탭)
  - render_hzt_item_md      →  "# 🚗 수평전개" 시작 (수평전개 탭)

섹션 라벨은 `_md_section_label` 이 만든 HTML `<td>...</td>` 안에 들어있어
정규식으로 매칭. 본문은 라벨 다음 ~ 다음 라벨/EOF 사이의 텍스트에서 HTML
태그를 제거해 추출한다.

Qt 의존 없음 — 순수 string / regex.
"""

import re


# ── 카테고리 식별 ───────────────────────────────────────────────
# 첫 줄의 H1 헤더로 카테고리 판별. 헤더 형식:
#   "# 📝 이슈 #N — title"
#   "# 📐 사양변경 — title"
#   "# 🚗 수평전개 — title"
_CAT_PATTERN = re.compile(
    r"^#\s*(?P<emoji>📝|📐|🚗)\s*(?P<word>이슈|사양변경|수평전개)"
    r"(?:\s*#(?P<idx>\d+))?"
    r"(?:\s*—\s*(?P<title>.+?))?\s*$",
    re.MULTILINE,
)

_EMOJI_TO_KEY = {
    "📝": "issue",
    "📐": "spec",
    "🚗": "hzt",
}


def detect_category(md: str) -> tuple:
    """본문 마크다운 → (category_key, title, idx_or_0).

    category_key: "issue" / "spec" / "hzt" / ""
    title: 제목 (없으면 "")
    idx_or_0: 이슈 번호 (이슈 카테고리에서만, 없으면 0)
    """
    text = str(md or "").strip()
    if not text:
        return ("", "", 0)
    m = _CAT_PATTERN.search(text)
    if not m:
        return ("", "", 0)
    key = _EMOJI_TO_KEY.get(m.group("emoji"), "")
    title = (m.group("title") or "").strip()
    try:
        idx = int(m.group("idx") or 0)
    except (TypeError, ValueError):
        idx = 0
    return (key, title, idx)


# ── 섹션 라벨 ──────────────────────────────────────────────────
# _md_section_label() 의 HTML <td>...</td> 안에 들어있는 텍스트 매칭.
# 라벨 별 키 매핑 (이슈/사양변경/수평전개 공통).
_SECTION_LABELS = {
    "issue": {
        "⚠️ 현상":         "phenom",
        "🔍 분석 내용":     "analysis",
        "✅ 대책":          "action",
        "🚗 수평전개":      "hzt_section",   # 표 위에 붙는 라벨
    },
    "spec": {
        "📐 변경 내용":     "content",
        "🕒 발생시점":      "occurrence",
        "🚗 수평전개":      "hzt_section",
    },
    "hzt": {
        "🚗 수평전개 내용": "content",
        "🕒 발생시점":      "occurrence",
        "🚗 적용 차종":     "hzt_section",
    },
}

# <td ...>섹션 라벨</td> 매칭용 — 라벨 텍스트 부분만 캡처
_SECTION_TD_RE = re.compile(
    r"<td[^>]*>\s*([^<]+?)\s*</td>",
    re.IGNORECASE,
)

# JIRA 링크 카드 안의 <a href="...">...</a> 추출
_JIRA_HREF_RE = re.compile(
    r'<a\s+[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>',
    re.IGNORECASE,
)


# ── HTML → 순수 텍스트 ─────────────────────────────────────────
def _strip_html(s: str) -> str:
    """HTML 태그 제거 + 엔티티 디코드 + 빈 줄 정리. 사용자 입력 복원용."""
    if not s:
        return ""
    # 줄 단위 처리 — <table>/<tr>/<td>/<br> 같은 블록 태그 흔적 제거
    # 1) <br>, <br/> → 개행
    s = re.sub(r"<br\s*/?\s*>", "\n", s, flags=re.IGNORECASE)
    # 2) <p>...</p> → 본문만 + 개행
    s = re.sub(r"</p\s*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<p[^>]*>", "", s, flags=re.IGNORECASE)
    # 3) 그 외 모든 태그 제거
    s = re.sub(r"<[^>]+>", "", s)
    # 4) 흔한 HTML 엔티티
    s = (s.replace("&nbsp;", " ")
          .replace("&amp;", "&")
          .replace("&lt;", "<")
          .replace("&gt;", ">")
          .replace("&quot;", '"')
          .replace("&#39;", "'"))
    # 5) 연속 공백 줄 → 1 줄
    s = re.sub(r"\n[ \t]+\n", "\n\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ── JIRA 링크 추출 ──────────────────────────────────────────────
def _extract_jira(md: str) -> str:
    """첫 번째 <a href="..."> 의 URL 을 JIRA 링크로 반환. 없으면 빈 문자열."""
    m = _JIRA_HREF_RE.search(md or "")
    return m.group(1).strip() if m else ""


# ── 섹션별 본문 추출 ───────────────────────────────────────────
def _extract_sections(md: str, category: str) -> dict:
    """본문 마크다운에서 카테고리별 섹션 라벨 마커로 본문 텍스트 추출.

    반환 dict 의 키는 _SECTION_LABELS[category] 의 value (phenom/analysis/...).
    매칭 안 된 섹션은 빈 문자열.
    """
    label_map = _SECTION_LABELS.get(category) or {}
    out: dict = {v: "" for v in label_map.values()}
    if not md or not label_map:
        return out

    # 라벨 매칭 위치들 + 라벨 텍스트 수집
    hits: list[tuple] = []   # [(start, end, key), ...]
    for m in _SECTION_TD_RE.finditer(md):
        label_text = (m.group(1) or "").strip()
        if label_text in label_map:
            hits.append((m.start(), m.end(), label_map[label_text]))

    if not hits:
        return out

    # 매칭 위치 사이의 본문 추출 — 마지막 매칭은 EOF 까지
    for i, (s, e, key) in enumerate(hits):
        body_start = e
        body_end   = hits[i + 1][0] if i + 1 < len(hits) else len(md)
        section_body = md[body_start:body_end]
        # </table></tr> 등 추가로 따라오는 닫는 태그 제거
        cleaned = _strip_html(section_body)
        # 첫 번째 _md_section_label() 의 </tr></table> 흔적 정리는 _strip_html 이 처리
        if cleaned and not out[key]:
            out[key] = cleaned

    return out


# ── 수평전개 차종 표 파싱 ───────────────────────────────────────
# _md_hzt_table 가 만든 HTML 표에서 차종별 상태 추출.
# 표 헤더 = <tr><th>차종1</th><th>차종2</th>...</tr>
# 본문   = <tr><td>적용/미적용/NA</td>...</tr>
_HZT_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_HZT_TH_RE = re.compile(r"<th[^>]*>(.*?)</th>",   re.IGNORECASE | re.DOTALL)
_HZT_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>",   re.IGNORECASE | re.DOTALL)


def _extract_hzt_table(md: str) -> dict:
    """본문 마크다운에서 수평전개 차종 표를 {차종: 상태} dict 로 추출.

    매칭 안 되면 빈 dict. 상태가 "미적용" 인 항목도 포함 (사용자가 확인 가능).
    """
    if not md:
        return {}
    out: dict = {}
    # 첫 두 개의 <tr> — 헤더 + 본문 (단일 row 표)
    trs = _HZT_TR_RE.findall(md)
    if len(trs) < 2:
        return out
    header_row, body_row = trs[0], trs[1]
    headers = [_strip_html(s).strip() for s in _HZT_TH_RE.findall(header_row)]
    values  = [_strip_html(s).strip() for s in _HZT_TD_RE.findall(body_row)]
    if not headers or not values:
        return out
    for h, v in zip(headers, values):
        if h:
            out[h] = v or "미적용"
    return out


# ══════════════════════════════════════════════════════════════
#  공개 API
# ══════════════════════════════════════════════════════════════
def parse_item_md(md: str) -> dict:
    """CB 이슈 본문(description 마크다운) → 폼 입력값 dict.

    반환 키:
      category : "issue" / "spec" / "hzt" / ""
      title    : str
      idx      : int (이슈 카테고리에서만 의미, 그 외 0)
      jira     : str (JIRA URL 또는 텍스트)
      phenom   : str (이슈 — 현상)
      analysis : str (이슈 — 분석 내용)
      action   : str (이슈 — 대책)
      content  : str (사양변경/수평전개 — 변경/수평전개 내용)
      occurrence: str (사양변경/수평전개 — 발생시점)
      hzt      : dict {차종: 상태}  — 수평전개 표
      raw_md   : str — 원본 마크다운 (편집 가능하도록 보존)

    매칭 실패해도 안전 — 모든 키는 빈 값/빈 dict 으로 채워짐.
    """
    text = str(md or "")
    category, title, idx = detect_category(text)

    out = {
        "category":   category,
        "title":      title,
        "idx":        idx,
        "jira":       _extract_jira(text),
        "phenom":     "",
        "analysis":   "",
        "action":     "",
        "content":    "",
        "occurrence": "",
        "hzt":        _extract_hzt_table(text),
        "raw_md":     text,
    }
    if category:
        sections = _extract_sections(text, category)
        for k in ("phenom", "analysis", "action", "content", "occurrence"):
            if sections.get(k):
                out[k] = sections[k]
    return out


def classify_items(items_with_md: list) -> dict:
    """이슈 dict 리스트 → 카테고리별로 분류된 dict.

    Args:
      items_with_md: [{"id": cb_id, "name": title, "description": md, ...}, ...]
                     각 dict 에 description 키가 있어야 한다.

    Returns:
      {
        "issue": [parsed_dict, ...],   # 이슈 카테고리
        "spec":  [parsed_dict, ...],   # 사양변경
        "hzt":   [parsed_dict, ...],   # 수평전개
        "other": [parsed_dict, ...],   # 카테고리 식별 불가
      }
      각 parsed_dict 에는 위 parse_item_md 결과 + 원본 cb_id 추가.
    """
    out = {"issue": [], "spec": [], "hzt": [], "other": []}
    for it in (items_with_md or []):
        if not isinstance(it, dict):
            continue
        md = it.get("description") or it.get("descriptionPlain") or ""
        parsed = parse_item_md(md)
        parsed["cb_id"]   = str(it.get("id") or "")
        parsed["cb_name"] = str(it.get("name") or it.get("summary") or "")
        bucket = parsed.get("category") or "other"
        if bucket not in out:
            bucket = "other"
        out[bucket].append(parsed)
    return out
