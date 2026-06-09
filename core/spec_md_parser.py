"""spec_md_parser.py — ① 사양 변경 페이지 마크다운 역파싱.

CB 트래커에 등록된 이슈의 description 마크다운을 파싱해 폼 입력값
(제목 / JIRA / 본문 / 발생시점 / 수평전개 표) 으로 복원한다.

파싱 대상 마크다운은 view.pages.page_spec 의 다음 메서드로 생성된 것:
  - render_change_item_md   →  "# 📝 이슈" 시작 (이슈 탭)
  - render_spec_change_md   →  "# 📐 사양변경" 시작 (사양변경 탭)
  - render_hzt_item_md      →  "# 🚗 수평전개" 시작 (수평전개 탭)

CB 가 description 포맷을 임의 변환할 수 있어 (HTML/Wiki/Plain) 카테고리
헤더와 섹션 라벨 모두 **다중 형식 매칭**을 시도한다:

  카테고리:
    1) MD heading   `# 📝 이슈 #1 — title`
    2) HTML h1~h3   `<h1>📝 이슈 #1 — title</h1>`
    3) 평문 emoji   `📝 이슈 #1 — title` (헤딩 마크업이 제거된 경우)

  섹션 라벨 (`_md_section_label` 의 HTML <td> 블록):
    1) HTML `<td...>라벨</td>`  (CB 가 HTML 그대로 보존)
    2) 평문 라벨 줄            (CB 가 wiki/plain 으로 변환한 경우)

Qt 의존 없음 — 순수 string / regex.
"""

import re


# ══════════════════════════════════════════════════════════════
#  카테고리 식별
# ══════════════════════════════════════════════════════════════
# 제목 구분자 — 업로드 시 `—` (em dash) 사용하지만 CB 가 `-` / `–` / `:`
# 로 정규화하는 경우도 흡수.
_TITLE_SEP = r"[—–\-:]"

# (0) SLAI 마커 — render_*_md 가 본문 최상단에 박는 HTML 주석.
#     CB 가 HTML 주석을 보존하면 카테고리/idx 를 100% 안정적으로 식별.
#     `<!-- SLAI:cat=issue idx=1 -->` 형식.
_SLAI_MARKER_RE = re.compile(
    r"<!--\s*SLAI\s*:\s*cat\s*=\s*(?P<cat>issue|spec|hzt)"
    r"(?:\s+idx\s*=\s*(?P<idx>\d+))?\s*-->",
    re.IGNORECASE,
)

# (1) MD heading 형식
_CAT_RE_MD = re.compile(
    r"^#\s*(?P<emoji>📝|📐|🚗)\s*(?P<word>이슈|사양변경|수평전개)"
    r"(?:\s*#(?P<idx>\d+))?"
    rf"(?:\s*{_TITLE_SEP}\s*(?P<title>[^\n]+?))?\s*$",
    re.MULTILINE,
)
# (2) HTML <h1>~<h3>
_CAT_RE_HTML = re.compile(
    r"<h[1-3][^>]*>\s*(?P<emoji>📝|📐|🚗)\s*(?P<word>이슈|사양변경|수평전개)"
    r"(?:\s*#(?P<idx>\d+))?"
    rf"(?:\s*{_TITLE_SEP}\s*(?P<title>[^<]+?))?\s*</h[1-3]>",
    re.IGNORECASE | re.DOTALL,
)
# (3) 평문 emoji 라인 (헤딩 마크업이 사라진 경우)
_CAT_RE_PLAIN = re.compile(
    r"(?:^|\n)[\s*_>|]*(?P<emoji>📝|📐|🚗)\s*(?P<word>이슈|사양변경|수평전개)"
    r"(?:\s*#(?P<idx>\d+))?"
    rf"(?:\s*{_TITLE_SEP}\s*(?P<title>[^\n]+?))?\s*(?:\n|$)",
)

_EMOJI_TO_KEY = {
    "📝": "issue",
    "📐": "spec",
    "🚗": "hzt",
}


def detect_category(md: str) -> tuple:
    """본문 → (category_key, title, idx_or_0).

    우선순위:
      (0) SLAI HTML 주석 마커 — render_*_md 가 박은 cat=issue/spec/hzt.
          CB 가 보존하면 가장 신뢰도 높음.
      (1) MD heading        — `# 📝 이슈 #1 — title`
      (2) HTML h1~h3        — `<h1>📝 이슈 #1 — title</h1>`
      (3) 평문 emoji 라인    — `📝 이슈 #1 — title`

    category_key: "issue" / "spec" / "hzt" / ""
    title: 헤딩에서 추출 (마커만 있는 경우엔 빈값 — 호출 측 폴백)
    """
    text = str(md or "").strip()
    if not text:
        return ("", "", 0)

    # (0) SLAI 마커 — 가장 신뢰. 단, title 은 헤딩에서 별도 추출.
    cat_from_marker = ""
    idx_from_marker = 0
    mm = _SLAI_MARKER_RE.search(text)
    if mm:
        cat_from_marker = mm.group("cat").lower()
        try:
            idx_from_marker = int(mm.group("idx") or 0)
        except (TypeError, ValueError):
            idx_from_marker = 0

    # (1)~(3) 헤딩 매칭 — title / idx 추출
    for pat in (_CAT_RE_MD, _CAT_RE_HTML, _CAT_RE_PLAIN):
        m = pat.search(text)
        if not m:
            continue
        key = _EMOJI_TO_KEY.get(m.group("emoji"), "")
        title = (m.group("title") or "").strip()
        title = re.sub(r"<[^>]+>", "", title).strip()
        try:
            idx = int(m.group("idx") or 0)
        except (TypeError, ValueError):
            idx = 0
        if cat_from_marker:
            # 마커 우선 — 헤딩에서 title 만 가져옴
            return (cat_from_marker, title, idx or idx_from_marker)
        if key:
            return (key, title, idx)

    # 헤딩 매칭 실패해도 마커만 있으면 카테고리는 식별 — title 은 빈값
    if cat_from_marker:
        return (cat_from_marker, "", idx_from_marker)
    return ("", "", 0)


# ══════════════════════════════════════════════════════════════
#  섹션 라벨
# ══════════════════════════════════════════════════════════════
# 카테고리별 라벨 — page_spec.py 의 _md_section_label() 인자와 1:1 매칭.
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

# 라벨에서 emoji 와 한글만 분리 (평문 매칭용) — emoji 가 사라져도 한글로 매칭.
def _label_text_only(label: str) -> str:
    """`⚠️ 현상` → `현상`, `🚗 수평전개 내용` → `수평전개 내용`."""
    # 모든 emoji/심볼 prefix 제거 — ASCII 외 + 공백 첫 어절 제거
    s = label.strip()
    # 첫 어절이 emoji 시퀀스면 제거
    s = re.sub(r"^[^\w가-힣]+", "", s)
    return s.strip()


# HTML <td>...</td> 매칭 (label 텍스트 캡처)
_SECTION_TD_RE = re.compile(
    r"<td[^>]*>\s*([^<]+?)\s*</td>",
    re.IGNORECASE,
)

# JIRA 링크 카드 안의 <a href="...">...</a> 추출
_JIRA_HREF_RE = re.compile(
    r'<a\s+[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>',
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════
#  HTML → 순수 텍스트
# ══════════════════════════════════════════════════════════════
def _strip_html(s: str) -> str:
    """HTML 태그 제거 + 엔티티 디코드 + 빈 줄 정리. 사용자 입력 복원용."""
    if not s:
        return ""
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


# ══════════════════════════════════════════════════════════════
#  JIRA 링크 추출
# ══════════════════════════════════════════════════════════════
def _extract_jira(md: str) -> str:
    """첫 번째 <a href="..."> 의 URL 을 JIRA 링크로 반환.

    HTML 링크가 없으면 평문 URL 패턴 (https?://...) 도 검색해서 폴백.
    """
    m = _JIRA_HREF_RE.search(md or "")
    if m:
        return m.group(1).strip()
    # 평문 URL 폴백 — 본문 어디에 JIRA URL 이 텍스트로만 남아있는 경우
    plain = re.search(
        r"(https?://[^\s<>'\"]+(?:jira|atlassian)[^\s<>'\"]*)",
        md or "", re.IGNORECASE)
    if plain:
        return plain.group(1).strip()
    return ""


# ══════════════════════════════════════════════════════════════
#  섹션 라벨 위치 수집 — HTML <td> 우선, 평문 폴백
# ══════════════════════════════════════════════════════════════
def _collect_label_hits(md: str, label_map: dict) -> list:
    """라벨 매칭 위치 + 키 리스트를 반환.

    1) HTML <td>...</td> 안의 라벨 텍스트로 먼저 시도.
    2) 0건이면 평문 (라벨 텍스트가 자체로 한 줄에 나타나는 경우) 시도.
       평문 매칭은 emoji 없이 한글만 있어도 OK (`현상`, `분석 내용` 등).

    반환: [(start, end, key), ...] — start 순 정렬.
    """
    if not md or not label_map:
        return []

    # ── (1) HTML <td>label</td> ─────────────────────────────
    hits: list = []
    for m in _SECTION_TD_RE.finditer(md):
        label_text = (m.group(1) or "").strip()
        # HTML 엔티티 디코드 (emoji 가 &amp; 같은 걸로 깨질 수 있음)
        label_text = (label_text
                      .replace("&nbsp;", " ")
                      .replace("&amp;", "&"))
        if label_text in label_map:
            hits.append((m.start(), m.end(), label_map[label_text]))
        else:
            # emoji 없는 비교 — `현상` ↔ `⚠️ 현상`
            stripped = _label_text_only(label_text)
            for full_label, key in label_map.items():
                if _label_text_only(full_label) == stripped and stripped:
                    hits.append((m.start(), m.end(), key))
                    break
    if hits:
        hits.sort(key=lambda t: t[0])
        return hits

    # ── (2) 평문 폴백 — 라벨 문자열을 본문에서 직접 검색 ──
    # 라벨 본 문자열 + emoji 없는 한글 변형 모두 후보.
    candidates = []   # [(label_pattern, key), ...]
    for full_label, key in label_map.items():
        plain = _label_text_only(full_label)
        if plain:
            candidates.append((plain, key))
        # emoji 포함 원본도 후보 (CB 가 보존한 경우)
        candidates.append((full_label, key))

    plain_hits: list = []
    for label_text, key in candidates:
        # 라벨이 자체적으로 한 줄(또는 단락) 첫 어절이어야 함 — 본문 중간의
        # 우연한 매칭은 피하도록 줄 시작/공백 경계로 제한.
        pat = re.compile(
            r"(?:^|\n)[\s>*_|]*" + re.escape(label_text) + r"\s*(?=\n|$)",
            re.MULTILINE,
        )
        for m in pat.finditer(md):
            plain_hits.append((m.start(), m.end(), key))

    # 같은 key 가 여러 번 잡혔으면 첫 번째만 유지 (라벨 중복 검색 방지)
    seen_keys: set = set()
    deduped: list = []
    for s, e, k in sorted(plain_hits, key=lambda t: t[0]):
        if k in seen_keys:
            continue
        seen_keys.add(k)
        deduped.append((s, e, k))
    return deduped


# ══════════════════════════════════════════════════════════════
#  섹션별 본문 추출
# ══════════════════════════════════════════════════════════════
def _extract_sections(md: str, category: str) -> dict:
    """본문 마크다운에서 카테고리별 섹션 라벨 마커로 본문 텍스트 추출.

    반환 dict 의 키는 _SECTION_LABELS[category] 의 value (phenom/analysis/...).
    매칭 안 된 섹션은 빈 문자열.
    """
    label_map = _SECTION_LABELS.get(category) or {}
    out: dict = {v: "" for v in label_map.values()}
    if not md or not label_map:
        return out

    hits = _collect_label_hits(md, label_map)
    if not hits:
        return out

    # 매칭 위치 사이의 본문 추출 — 마지막 매칭은 EOF 까지
    for i, (s, e, key) in enumerate(hits):
        body_start = e
        body_end   = hits[i + 1][0] if i + 1 < len(hits) else len(md)
        section_body = md[body_start:body_end]
        cleaned = _strip_html(section_body)
        if cleaned and not out[key]:
            out[key] = cleaned

    return out


# ══════════════════════════════════════════════════════════════
#  수평전개 차종 표 파싱
# ══════════════════════════════════════════════════════════════
# _md_hzt_table 가 만든 HTML 표에서 차종별 상태 추출.
# 표 헤더 = <tr><th>차종1</th><th>차종2</th>...</tr>
# 본문   = <tr><td>적용/미적용/NA</td>...</tr>
_HZT_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_HZT_TH_RE = re.compile(r"<th[^>]*>(.*?)</th>",   re.IGNORECASE | re.DOTALL)
_HZT_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>",   re.IGNORECASE | re.DOTALL)


def _extract_hzt_table(md: str) -> dict:
    """본문 마크다운에서 수평전개 차종 표를 {차종: 상태} dict 로 추출.

    매칭 안 되면 빈 dict. 상태가 "미적용" 인 항목도 포함 (사용자가 확인 가능).
    여러 <table> 중 차종이 들어있는 표를 자동 식별 (헤더에 알려진 차종 키워드
    가 하나라도 포함된 표 선택).
    """
    if not md:
        return {}

    # ── 차종 표 후보 키워드 (헤더에 1개라도 있으면 차종 표로 간주) ──
    # page_spec.VEHICLE_COLUMNS 의 prefix — 'NQ5', 'MQ4' 등 부분 매칭
    VEHICLE_HINTS = ("NQ5", "MQ4", "LX3", "JW", "TK1", "LQ2", "SP3",
                     "KU", "SG2", "NX5", "SX3", "Qy2", "NQ6")

    # 모든 <tr> 추출
    trs = _HZT_TR_RE.findall(md)
    if len(trs) < 2:
        return {}

    # 헤더 후보 찾기 — 차종 키워드가 1개라도 있는 <tr> 의 인덱스
    header_idx = -1
    for idx, tr in enumerate(trs):
        ths = _HZT_TH_RE.findall(tr)
        cells = ths or _HZT_TD_RE.findall(tr)   # th 없으면 td 도 허용
        header_text = " ".join(_strip_html(c) for c in cells)
        if any(hint in header_text for hint in VEHICLE_HINTS):
            header_idx = idx
            break
    if header_idx < 0 or header_idx + 1 >= len(trs):
        return {}

    header_row = trs[header_idx]
    body_row   = trs[header_idx + 1]

    # 헤더: th 우선, 없으면 td 도 허용
    headers = [_strip_html(s).strip() for s in _HZT_TH_RE.findall(header_row)]
    if not headers:
        headers = [_strip_html(s).strip() for s in _HZT_TD_RE.findall(header_row)]
    values  = [_strip_html(s).strip() for s in _HZT_TD_RE.findall(body_row)]
    if not headers or not values:
        return {}

    # 첫 컬럼이 '차종' 같은 라벨이면 스킵 (행 헤더)
    if headers and headers[0] in ("차종", ""):
        headers = headers[1:]
    if values and values[0] in ("적용 여부", ""):
        values = values[1:]

    out: dict = {}
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


def _guess_category_from_content(md: str, parsed: dict) -> str:
    """헤딩/마커 모두 실패한 경우 본문 내용으로 카테고리 추정.

    힌트:
      · '현상' / '분석 내용' / '대책' 중 1개라도 있음 → issue
      · '변경 내용' 있음 → spec
      · '수평전개 내용' / '적용 차종' 있음 → hzt
      · 그 외 → issue (가장 일반적인 카테고리로 폴백 — 사용자가 수동 편집 가능)
    """
    # parsed 가 이미 시도해본 결과를 보유
    if parsed.get("phenom") or parsed.get("analysis") or parsed.get("action"):
        return "issue"
    text = md or ""
    if any(label in text for label in ("🔍 분석 내용", "분석 내용", "⚠️ 현상", "대책", "✅ 대책")):
        return "issue"
    if any(label in text for label in ("📐 변경 내용", "변경 내용", "사양변경")):
        return "spec"
    if any(label in text for label in ("🚗 수평전개 내용", "수평전개 내용", "적용 차종")):
        return "hzt"
    # 마지막 폴백 — 이슈 탭으로 (가장 일반적 — 사용자가 검토 후 이동/편집)
    return "issue"


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
        "other": [parsed_dict, ...],   # 비어있음 (휴리스틱으로 모두 분배)
      }
      각 parsed_dict 에는 위 parse_item_md 결과 + 원본 cb_id 추가.
      마커/헤딩으로 식별 실패 시:
        · 본문 내용에서 라벨 (현상/대책/...) 을 찾아 카테고리 추정
        · 추정도 실패하면 'issue' 탭으로 폴백 (사용자가 수동 편집 가능)
      → "other" 버킷에는 description 이 완전히 빈 항목만 남는다.

      title 도 비어있으면 CB 이슈 제목으로 폴백 — 사용자가 식별 가능하도록.
    """
    out = {"issue": [], "spec": [], "hzt": [], "other": []}
    for it in (items_with_md or []):
        if not isinstance(it, dict):
            continue
        md = it.get("description") or it.get("descriptionPlain") or ""
        parsed = parse_item_md(md)
        parsed["cb_id"]   = str(it.get("id") or "")
        parsed["cb_name"] = str(it.get("name") or it.get("summary") or "")
        if not parsed.get("title"):
            parsed["title"] = parsed["cb_name"]

        cat = parsed.get("category") or ""
        if not cat:
            # description 이 완전히 비었으면 other 로 (스킵 표시)
            if not (md or "").strip():
                bucket = "other"
            else:
                # 본문 내용으로 카테고리 추정 — 실패해도 issue 폴백
                bucket = _guess_category_from_content(md, parsed)
                parsed["category"] = bucket   # 폴백 결과 반영
                parsed["category_guessed"] = True
        else:
            bucket = cat
        if bucket not in out:
            bucket = "other"
        out[bucket].append(parsed)
    return out
