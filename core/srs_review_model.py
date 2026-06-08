"""srs_review_model.py — SRS 검토 세션 데이터 모델.

새 워크플로우 (사진 5단계 운영 플로우 기반, 2026-06-04 재설계):
  1. 변경사항 접수 — 요구사항 입력 + CB 변경점 fetch + 과거차 fetch
  2. 설계자 직접 검토 — 공통 체크리스트 5행 + 4역할(SYS/SW/HW/TEST) 검토 의견
  3. 검토 회의 — 회의록 (쟁점/결정/액션아이템)
  4. 체크리스트 보정 — 회의 결과 반영 (잠금/수정 토글)
  5. AI 인사이트 — 변경점별 병렬 AI 호출 + 개별 결과

데이터 분리 원칙:
  - **공통 입력 (CommonInputs)** — 변경점 묶음 전체에 1세트
    체크리스트 5행 / 4역할 검토 의견 / 회의록 / (옵션) 요구사항 DIFF
  - **변경점별 데이터 (ChangeItemAnalysis)** — N개
    cb_item / ai_result
  - **과거차 (historical_issues)** — 공통, CB 과거차 트래커 fetch 결과

JSON 직렬화/역직렬화 — srs_review_state.json 자동 저장/복원에 사용
(spec_state.json 과 동일 패턴, main.py closeEvent / __init__ 에서 호출).
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


# ══════════════════════════════════════════════════════════════
#  CommonInputs — 변경점 묶음 전체에 공통 적용되는 입력
# ══════════════════════════════════════════════════════════════
@dataclass
class CommonInputs:
    """묶음 전체에 1세트만 존재하는 공통 입력 데이터.

    Attributes:
        checklist        : 고정 체크리스트 5행 작성결과
                          {section_id: "작성 내용 문자열"}
                          section_id 는 prompts/checklists/srs_review_default.json
                          의 fixed_checklist[].id 와 일치 (intent/target/impact/
                          evidence/owners)
        reviews          : 4역할 설계자 검토 의견
                          {"sys": "...", "sw": "...", "hw": "...", "test": "..."}
        meeting          : 회의록
                          {
                            "issues":       "쟁점 본문",
                            "decisions":    "결정사항 본문",
                            "action_items": [
                              {"action": "...", "owner": "...",
                               "due": "...", "status": "대기"},
                              ...
                            ]
                          }
        req_diff         : (옵션) 요구사항 DIFF 텍스트.
                          비어있지 않으면 AI 분석 시 "요구사항-변경점 매칭" 섹션 추가.
        checklist_locked : 체크리스트 잠금 여부.
                          True → readonly (회색 처리), [수정] 버튼으로 토글 해제.
    """
    checklist:        dict = field(default_factory=dict)
    reviews:          dict = field(default_factory=dict)
    meeting:          dict = field(default_factory=dict)
    req_diff:         str  = ""
    checklist_locked: bool = False


# ══════════════════════════════════════════════════════════════
#  ChangeItemAnalysis — 변경점 1개 + AI 결과
# ══════════════════════════════════════════════════════════════
@dataclass
class ChangeItemAnalysis:
    """변경점 1개 단위 데이터.

    Attributes:
        cb_item   : CB 트래커에서 fetch 한 변경점 원본 dict
                    (id, title, description, status, owner 등 — fetcher 결과 그대로)
        ai_result : AI 분석 결과 dict | None
                    Worker 가 채워주는 5(+1)섹션 구조 :
                      {
                        "similar_past":     "마크다운 본문",
                        "missing":          "...",
                        "questions_per_role": {...},
                        "recurrence_top3":  "...",
                        "limitation":       "고정 문구",
                        "req_diff_match":   "..."   # req_diff 있을 때만
                      }
                    None = 아직 분석 안 됨.
    """
    cb_item:   dict           = field(default_factory=dict)
    ai_result: Optional[dict] = None


# ══════════════════════════════════════════════════════════════
#  SrsReviewSession — 세션 전체 (JSON 저장/복원 단위)
# ══════════════════════════════════════════════════════════════
@dataclass
class SrsReviewSession:
    """SRS 검토 세션 전체 상태 — srs_review_state.json 직렬화 단위."""
    common:            CommonInputs = field(default_factory=CommonInputs)
    items:             list         = field(default_factory=list)   # list[ChangeItemAnalysis]
    historical_issues: list         = field(default_factory=list)   # list[dict]

    # ── JSON 직렬화 ──────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "common":            asdict(self.common),
            "items":             [asdict(it) for it in self.items],
            "historical_issues": list(self.historical_issues),
        }

    # ── JSON 역직렬화 (백워드 호환 폴백 포함) ─────────────────
    @classmethod
    def from_dict(cls, data: dict) -> "SrsReviewSession":
        if not isinstance(data, dict):
            return cls()
        common_d = data.get("common") or {}
        common = CommonInputs(
            checklist        = common_d.get("checklist") or {},
            reviews          = common_d.get("reviews")   or {},
            meeting          = common_d.get("meeting")   or {},
            req_diff         = common_d.get("req_diff")  or "",
            checklist_locked = bool(common_d.get("checklist_locked", False)),
        )
        items: list = []
        for it_d in (data.get("items") or []):
            if isinstance(it_d, dict):
                items.append(ChangeItemAnalysis(
                    cb_item   = it_d.get("cb_item") or {},
                    ai_result = it_d.get("ai_result"),
                ))
        return cls(
            common            = common,
            items             = items,
            historical_issues = data.get("historical_issues") or [],
        )
