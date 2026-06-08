"""config.py — Codebeamer 통합용 설정·경로·상수.

Qt 의존 없음 — 순수 파일 I/O + json.
"""

import os
import re
import sys
import json


# ── 파일 경로 ──────────────────────────────────────────────────
def _get_data_dir() -> str:
    """사용자 데이터(설정/CB 캐시 MD) 저장 폴더를 반환.
      - EXE(PyInstaller frozen) 실행 시: %APPDATA%\\CodeReviewer
      - 개발 환경(python 직접 실행) 시 : 프로젝트 루트
        (이 파일이 integrations/codebeamer/ 안에 있으므로 부모 디렉터리로 두 단계 더 올라간다)
    """
    if getattr(sys, "frozen", False):
        base = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "CodeReviewer",
        )
    else:
        # integrations/codebeamer/config.py → 프로젝트 루트
        # config.py → codebeamer/ → integrations/ → project_root  (dirname 3번)
        base = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
    os.makedirs(base, exist_ok=True)
    return base


_BASE       = _get_data_dir()
CB_CFG_FILE = os.path.join(_BASE, "cb_config.json")
CB_MD_FILE  = os.path.join(_BASE, "cb_context.md")

# ── 대상 트래커 목록 (이름 : 트래커 ID) ────────────────────────
TRACKER_DEFS = [
    ("ILCU", "8416257"),
    ("LDM",  "8417515"),
    ("SAL",  "8559489"),
    ("BLTN", "8559570"),
    ("DSM",  "8559651"),
    ("PLBM", "8559814"),
    ("SBCM", "8559733"),
    ("SBW",  "8559895"),
    ("WPC",  "8559976"),
]


# ══════════════════════════════════════════════════════════════
#  설정 로드 / 저장
# ══════════════════════════════════════════════════════════════
def _default_cfg() -> dict:
    d = {"url": "https://codebeamer.slworld.com/cb", "username": "", "password": ""}
    for name, tid in TRACKER_DEFS:
        d[f"tracker_{name.lower()}"] = tid
    # section_past 는 TRACKER_DEFS 로 미리 채워 둠 — 사용자는 ID/PW만 입력하면 바로 사용 가능
    d["section_past"]  = {name: tid for name, tid in TRACKER_DEFS}
    # [LL/SWE DISABLED] section_ll / section_swe1 / section_swe3 는
    # 더 이상 사용하지 않으므로 디폴트에서 제외 (load 시 stored 에서도 자동 제거).
    # ── AI 리뷰 결과 업로드 — 마지막 사용값 기억 ─────────────────
    d["last_upload_tracker_id"] = ""
    d["last_upload_parent_id"]  = ""
    d["last_upload_attach_md"]  = True
    d["last_upload_attach_html"]= True
    # ── SRS 검토 페이지 — 마지막 사용 트래커 ID ──────────────────
    # 체크시트는 prompts/checklists/srs_review_default.json 프리셋에서 로드하므로
    # 마스터 트래커 ID 는 보유하지 않는다.
    d["last_srs_source_tracker_id"] = ""   # 사양변경 트래커 (분석 원본)
    d["last_srs_result_tracker_id"] = ""   # SRS 검토 결과 등록 트래커
    # ── 수평전개 동기 등록 — 마지막 사용값 ───────────────────────
    d["last_hzt_enabled"]     = False
    d["last_hzt_tracker_id"]  = ""
    return d


# ── 입력값 → 트래커/이슈 ID 정규화 ──────────────────────────────
def parse_tracker_id_from_url(s: str) -> str:
    """CB URL → 트래커 ID(숫자) 추출.

    허용 형식:
      • 'https://.../cb/tracker/9486521'  → '9486521'   (정식)
      • 'https://.../cb/wiki/9498312'     → '9498312'   (위키 페이지 ID 도 허용)
      • 'https://.../cb/{anything}/{NUM}' → '{NUM}'     (마지막 경로의 숫자)
      • '9486521'                         → '9486521'   (숫자만)

    /tracker/ 가 아닌 경로(/wiki/, /issue/ 등)에서 추출한 숫자가 실제로
    트래커 ID 가 아니면 업로드 시 CB API 에서 에러가 발생할 수 있다.
    """
    s = (s or "").strip()
    if not s:
        return ""
    # 우선순위 1) /tracker/{ID} — 정식 트래커 URL
    m = re.search(r"/tracker/(\d+)", s)
    if m:
        return m.group(1)
    # 우선순위 2) /{경로}/{ID} — 위키/이슈 등 다른 CB 경로의 숫자도 허용
    m = re.search(r"/[A-Za-z]+/(\d+)(?:[/?#]|$)", s)
    if m:
        return m.group(1)
    # 우선순위 3) 순수 숫자만
    return s if s.isdigit() else ""


def parse_item_id_from_url(s: str) -> str:
    """'https://.../cb/issue/9499000' 또는 'item/9499000' 또는 '9499000' → '9499000'."""
    s = (s or "").strip()
    if not s:
        return ""
    m = re.search(r"/(?:issue|item)/(\d+)", s)
    if m:
        return m.group(1)
    return s if s.isdigit() else ""


# 더 이상 사용하지 않는 레거시 키 — load 시 stored 에서 발견되면 자동 제거.
_LEGACY_KEYS = ("section_ll", "section_swe1", "section_swe3")


def load_config() -> dict:
    default = _default_cfg()
    if not os.path.exists(CB_CFG_FILE):
        # 최초 실행 시 기본값(트래커 포함)으로 파일 생성
        try:
            os.makedirs(os.path.dirname(CB_CFG_FILE), exist_ok=True)
            with open(CB_CFG_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return default
    try:
        with open(CB_CFG_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)

        # 레거시 키 정리 — 발견 시 stored 에서 pop 하고 디스크에도 즉시 반영
        had_legacy = any(k in stored for k in _LEGACY_KEYS)
        for k in _LEGACY_KEYS:
            stored.pop(k, None)
        if had_legacy:
            try:
                with open(CB_CFG_FILE, "w", encoding="utf-8") as f:
                    json.dump(stored, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        merged = {**default, **stored}
        # 저장된 section_past 가 비어있으면 기본 트래커로 복원
        if not stored.get("section_past"):
            merged["section_past"] = default["section_past"]
        return merged
    except Exception:
        pass
    return default


def save_config(cfg: dict):
    try:
        # 레거시 키 안전망 — 호출자가 실수로 넘겨도 디스크엔 쓰지 않는다
        cfg = {k: v for k, v in (cfg or {}).items() if k not in _LEGACY_KEYS}
        with open(CB_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#  헬퍼: 저장된 cb_context.md 로드
# ══════════════════════════════════════════════════════════════
def load_cb_context(path: str = None) -> str:
    path = path or CB_MD_FILE
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        pass
    return ""
