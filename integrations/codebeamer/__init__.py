"""integrations.codebeamer — Codebeamer 연동 패키지.

이 패키지는 기존의 단일 파일 `codebeamer.py` (4,000+ 줄) 를 분할해 만든 것이다.
외부에서는 기존과 동일한 import 경로 (`from integrations.codebeamer import ...`) 로
공개 API 에 접근할 수 있도록 본 __init__.py 가 모든 공개 심볼을 재수출한다.

내부 구성:
  config.py         ← _BASE / CB_CFG_FILE / CB_MD_FILE / TRACKER_DEFS
                       load_config / save_config / parse_*  / load_cb_context
  text.py           ← _clean_text  (HTML/위키마크업 정제)
  api.py            ← CbFetcher    (REST API 클라이언트)
  ui_primitives.py  ← _ca / _ClickableWidget / _ElidedLabel / _FetchWorker
  dialogs.py        ← CbConfigDialog / _FetchSelectDialog
  section_widget.py ← CbSectionWidget  (4분할 탭 개별 섹션)

외부 import 사용처:
  - controllers/cb_controller.py : CbConfigDialog, load_cb_context, _BASE,
                                    CbFetcher, load_config, save_config
  - controllers/ai_controller.py : _BASE
  - view/ui_input.py             : CbFetcher, save_config, load_config
  - view/ui_cb_upload.py         : parse_tracker_id_from_url, parse_item_id_from_url
  - view/ui_result.py            : CbSectionWidget
"""

# 공개 API 재수출 — 외부 import 가 그대로 작동하도록
from .api import CbFetcher
from .config import (
    CB_CFG_FILE,
    CB_MD_FILE,
    TRACKER_DEFS,
    _BASE,
    _default_cfg,
    load_cb_context,
    load_config,
    parse_item_id_from_url,
    parse_tracker_id_from_url,
    save_config,
)
from .dialogs import CbConfigDialog
from .section_widget import CbSectionWidget
from .text import _clean_text


__all__ = [
    # config
    "_BASE", "CB_CFG_FILE", "CB_MD_FILE", "TRACKER_DEFS",
    "load_config", "save_config", "load_cb_context",
    "parse_tracker_id_from_url", "parse_item_id_from_url",
    # api
    "CbFetcher",
    # ui
    "CbConfigDialog", "CbSectionWidget",
    # text
    "_clean_text",
]
