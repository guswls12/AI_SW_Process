"""controllers — MainWindow 의 흐름 제어 책임을 영역별로 분리한 패키지.

각 컨트롤러는 평범한 클래스로 구현되며,
MainWindow 가 자기 자신을 인자로 넘겨 컨트롤러를 보유한다 (ui_save.py 패턴).

  cb_controller.py    — Codebeamer 컨텍스트 로드 / 다이얼로그
  diff_controller.py  — DIFF 워커 라이프사이클 (단일/폴더/요구사항)
  ai_controller.py    — Claude API 호출 흐름 + 결과 라우팅

main.py 는 `from controllers.xxx_controller import XxxController` 처럼
모듈 경로로 직접 import 한다.
"""
