# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('prompts', 'prompts'),   # CERT-C / MISRA-C 규칙 MD → %APPDATA%\CodeReviewer\prompts 에 배포
        ('assets',  'assets'),    # 앱 아이콘 (app_icon.svg) 등 정적 리소스
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AI_CodeReview1.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # ⚠ .exe 파일 자체의 작업표시줄 아이콘은 .ico 포맷 필요.
    # SVG → ICO 변환 후 아래 주석 해제:
    #   icon='assets/app_icon.ico',
    # (런타임 윈도우 아이콘은 main.py setWindowIcon(SVG)로 이미 처리됨)
)
