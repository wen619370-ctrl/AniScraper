# -*- mode: python ; coding: utf-8 -*-
import os

# 获取当前脚本所在目录的绝对路径
spec_dir = os.path.dirname(os.path.abspath(SPEC))
media_scraper_dir = os.path.join(spec_dir, 'media_scraper_app')

a = Analysis(
    [os.path.join(media_scraper_dir, 'main.py')],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(media_scraper_dir, 'config.json'), '.'),
        (os.path.join(media_scraper_dir, 'resources'), 'resources')
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
    icon=[os.path.join(media_scraper_dir, 'resources', 'icons', 'app.ico')],
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
