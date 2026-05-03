# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['media_scraper_app\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('d:\\代码相关学习\\python\\个人项目\\类tmm\\media_scraper_app\\config.json', '.'), ('d:\\代码相关学习\\python\\个人项目\\类tmm\\media_scraper_app\\resources', 'resources')],
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
    [],
    exclude_binaries=True,
    name='AniScraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['d:\\代码相关学习\\python\\个人项目\\类tmm\\media_scraper_app\\resources\\icons\\app.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AniScraper',
)
