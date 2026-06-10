"""project_state.py — 프로젝트 + 버전 기반 상태 영속화 모듈.

프로그램 시작 시 ProjectStartDialog 에서 입력한 (프로젝트명, 버전) 을 키로
한 사이클의 모든 상태 (페이지별 트래커 ID + ⑧/⑨ 입력값) 를 별도 JSON 파일
에 저장한다.

파일 위치:
  <_BASE>/<sanitized_project>_<sanitized_version>.json
  - _BASE 는 integrations.codebeamer 와 동일 데이터 디렉터리
    (EXE 모드 = %APPDATA%/CodeReviewer, 개발 모드 = 프로젝트 루트)

여러 프로젝트 / 여러 버전을 동시 진행할 수 있도록 1:1 매핑 (프로젝트_버전 →
파일 1개). 시작 다이얼로그의 [📂 기존 파일 불러오기] 가 이 폴더에서 .json
파일 목록을 보여준다.

Qt 의존 없음 — 순수 파일 I/O + json.
"""

import os
import re
import json
import glob

from integrations.codebeamer.config import _BASE


# ── 페이지 키 ── 9 탭 사이드바 (① ~ ⑨)
PAGE_KEYS = (
    "spec",    # ① 사양 변경
    "srs",     # ② SWE.1 SRS
    "sad",     # ③ SWE.2 SAD
    "sdd",     # ④ SWE.3/4 SDD
    "static",  # ⑤ 정적 검증 결과
    "review",  # ⑥ 코드리뷰 결과
    "test",    # ⑦ 설계자 테스트 결과
    "open",    # ⑧ OPEN 항목 및 잔여 조치
    "deploy",  # ⑨ 배포 리뷰
)

PAGE_LABELS = {
    "spec":   "① 사양 변경",
    "srs":    "② SWE.1 SRS",
    "sad":    "③ SWE.2 SAD",
    "sdd":    "④ SWE.3/4 SDD",
    "static": "⑤ 정적 검증 결과",
    "review": "⑥ 코드리뷰 결과",
    "test":   "⑦ 설계자 테스트 결과",
    "open":   "⑧ OPEN 항목 및 잔여 조치",
    "deploy": "⑨ 배포 리뷰",
}

# Codebeamer 트래커 URL 패턴
CB_TRACKER_URL_FMT = "https://codebeamer.slworld.com/cb/tracker/{tid}"
CB_ISSUE_URL_FMT   = "https://codebeamer.slworld.com/cb/issue/{iid}"

# 파일명 접미사
_FILE_SUFFIX = ".json"


# ══════════════════════════════════════════════════════════════
#  파일 경로 헬퍼
# ══════════════════════════════════════════════════════════════
def _sanitize(s: str) -> str:
    """프로젝트명/버전을 파일명 안전 문자열로 변환.

    영문자/숫자/한글/언더스코어/하이픈/점 만 남기고 그 외는 _ 로.
    공백은 _ 로. 빈 문자열은 빈 문자열 반환.
    """
    s = (s or "").strip()
    if not s:
        return ""
    # 공백 → _
    s = re.sub(r"\s+", "_", s)
    # 허용 문자 외 → _
    return re.sub(r"[^\w가-힣.\-]", "_", s)


def state_path(project_name: str, version: str) -> str:
    """JSON 파일의 절대 경로. 둘 중 하나라도 비어있으면 빈 문자열."""
    p = _sanitize(project_name)
    v = _sanitize(version)
    if not p or not v:
        return ""
    return os.path.join(_BASE, f"{p}_{v}{_FILE_SUFFIX}")


def state_dir() -> str:
    """JSON 파일들이 저장되는 디렉터리 (불러오기 다이얼로그용)."""
    return _BASE


def parse_filename(path: str) -> tuple:
    """파일 경로 → (project_name, version) 튜플. 형식 안 맞으면 ('', '')."""
    base = os.path.basename(path or "")
    if not base.endswith(_FILE_SUFFIX):
        return ("", "")
    stem = base[:-len(_FILE_SUFFIX)]
    # 마지막 '_' 이전 = project, 이후 = version
    # (프로젝트명에 '_' 가 있을 수 있으니 rsplit 사용)
    if "_" not in stem:
        return (stem, "")
    project, version = stem.rsplit("_", 1)
    return (project, version)


# ══════════════════════════════════════════════════════════════
#  기본 상태 구조
# ══════════════════════════════════════════════════════════════
def default_state(project_name: str = "", version: str = "") -> dict:
    """비어있는 상태 dict 의 기본 형태 — JSON 로드 실패 시 폴백."""
    return {
        "project_name": project_name or "",
        "version":      version or "",
        # 페이지별 트래커 ID (① ~ ⑨)
        "trackers":     {k: "" for k in PAGE_KEYS},
        # ⑧ OPEN 항목 페이지 입력값 (결과 라벨 + 코멘트)
        "open_items": {
            "static":      {"result": "", "comment": ""},
            "review_high": {"result": "", "comment": ""},
            "review_mid":  {"result": "", "comment": ""},
            "review_low":  {"result": "", "comment": ""},
            "test":        {"result": "", "comment": ""},
        },
        # ⑨ 배포 리뷰 — 결재란 (배포 승인자는 CB 에서 입력하므로 빈 값 유지)
        "deploy_review": {
            "approvals": {
                "writer":   {"dept": "", "name": "", "date": ""},
                "reviewer": {"dept": "", "name": "", "date": ""},
                "approver": {"dept": "", "name": "", "date": ""},
            },
        },
    }


# ══════════════════════════════════════════════════════════════
#  Load / Save
# ══════════════════════════════════════════════════════════════
def load_state(project_name: str, version: str) -> dict:
    """프로젝트+버전 상태 로드. 파일 없거나 손상되면 default_state 반환.

    누락된 키들은 default_state 로 보강 (스키마 진화 안전).
    """
    path = state_path(project_name, version)
    base = default_state(project_name, version)
    if not path or not os.path.exists(path):
        return base
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return base
    except (OSError, json.JSONDecodeError):
        return base

    out = base
    out["project_name"] = data.get("project_name") or project_name or ""
    out["version"]      = data.get("version")      or version      or ""
    out["trackers"].update(data.get("trackers") or {})
    for k, v in (data.get("open_items") or {}).items():
        if k in out["open_items"] and isinstance(v, dict):
            out["open_items"][k].update(v)
    dr = data.get("deploy_review") or {}
    for role, vals in (dr.get("approvals") or {}).items():
        if role in out["deploy_review"]["approvals"] and isinstance(vals, dict):
            out["deploy_review"]["approvals"][role].update(vals)
    return out


def load_state_from_path(path: str) -> dict:
    """절대 경로로 직접 state 로드 — 불러오기 다이얼로그가 파일 선택 후 호출."""
    proj, ver = parse_filename(path)
    return load_state(proj, ver)


def save_state(project_name: str, version: str, state: dict) -> bool:
    """프로젝트+버전 상태 저장. 두 값 다 있어야 저장 가능."""
    path = state_path(project_name, version)
    if not path:
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # 메타 키 보강
        state = dict(state or {})
        state.setdefault("project_name", project_name)
        state.setdefault("version", version)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


# ══════════════════════════════════════════════════════════════
#  트래커 ID — 페이지별 단축 API
# ══════════════════════════════════════════════════════════════
def get_tracker_id(project_name: str, version: str, page_key: str) -> str:
    """페이지의 트래커 ID. 없거나 키 잘못이면 빈 문자열."""
    if page_key not in PAGE_KEYS:
        return ""
    state = load_state(project_name, version)
    return str(state.get("trackers", {}).get(page_key, "") or "")


def set_tracker_id(project_name: str, version: str,
                   page_key: str, tracker_id: str) -> bool:
    """페이지의 트래커 ID 갱신 + 디스크 저장."""
    if page_key not in PAGE_KEYS:
        return False
    state = load_state(project_name, version)
    state.setdefault("trackers", {})[page_key] = str(tracker_id or "").strip()
    return save_state(project_name, version, state)


def get_all_trackers(project_name: str, version: str) -> dict:
    """{page_key: tracker_id} dict 반환."""
    state = load_state(project_name, version)
    return dict(state.get("trackers") or {})


def set_all_trackers(project_name: str, version: str,
                     trackers: dict) -> bool:
    """9개 트래커 ID 를 한 번에 저장 (시작 다이얼로그용).

    PAGE_KEYS 외 키는 무시. 빈 값은 그대로 빈 값으로 저장.
    """
    state = load_state(project_name, version)
    trk = state.setdefault("trackers", {})
    for k in PAGE_KEYS:
        if k in (trackers or {}):
            trk[k] = str(trackers[k] or "").strip()
    return save_state(project_name, version, state)


def build_tracker_url(tracker_id: str) -> str:
    """트래커(컨테이너) URL — '/cb/tracker/{ID}' 형태."""
    tid = str(tracker_id or "").strip()
    if not tid:
        return ""
    return CB_TRACKER_URL_FMT.format(tid=tid)


def build_issue_url(issue_id: str) -> str:
    """이슈(개별 항목) URL — '/cb/issue/{ID}' 형태.
    ⑨ 배포리뷰 등에서 등록된 이슈 ID 를 표시할 때 사용.
    """
    iid = str(issue_id or "").strip()
    if not iid:
        return ""
    return CB_ISSUE_URL_FMT.format(iid=iid)


# ══════════════════════════════════════════════════════════════
#  파일 목록 (시작 다이얼로그 '불러오기' 용)
# ══════════════════════════════════════════════════════════════
def list_state_files() -> list[dict]:
    """state_dir() 안의 모든 <project>_<version>.json 파일 메타 리스트.

    반환 형식:
      [{"path": ..., "project": "...", "version": "...",
        "modified": float_timestamp}, ...]
      수정일 내림차순 정렬 (가장 최근 작업이 위).

    다른 JSON (cb_config.json, srs_review_state.json, spec_state.json 등) 은
    제외하기 위해 '_' 가 stem 에 1개 이상 있는 파일만.
    """
    out = []
    pattern = os.path.join(_BASE, f"*{_FILE_SUFFIX}")
    # 시스템 JSON 파일들 — 목록에서 제외
    EXCLUDE = {
        "cb_config.json",
        "srs_review_state.json",
        "spec_state.json",
    }
    for path in glob.glob(pattern):
        base = os.path.basename(path)
        if base in EXCLUDE:
            continue
        stem = base[:-len(_FILE_SUFFIX)]
        # <project>_<version> 형식 — stem 에 '_' 가 있어야 한다
        if "_" not in stem:
            continue
        project, version = parse_filename(path)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        out.append({
            "path":     path,
            "project":  project,
            "version":  version,
            "modified": mtime,
        })
    out.sort(key=lambda d: d["modified"], reverse=True)
    return out


def url_to_tracker_id(s: str) -> str:
    """URL 또는 ID 문자열 → 숫자 ID 추출. 정규식 실패 시 입력 그대로 strip 후 반환.

    예:
      'https://codebeamer.slworld.com/cb/tracker/9924076' → '9924076'
      '9924076' → '9924076'
      '' → ''
    """
    s = str(s or "").strip()
    if not s:
        return ""
    m = re.search(r"/tracker/(\d+)", s)
    if m:
        return m.group(1)
    m = re.search(r"(\d+)$", s)
    if m:
        return m.group(1)
    return s
