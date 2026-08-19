# -*- mode: python ; coding: utf-8 -*-
# Build this spec ON macOS:  python -m PyInstaller --noconfirm --clean packaging/macos/GrooveTrainer.spec

from pathlib import Path

project_dir = Path(SPECPATH).resolve().parents[1]

a = Analysis(
    [str(project_dir / 'main.py')],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[
        (str(project_dir / 'assets' / 'woods'), 'assets/woods'),
        (str(project_dir / 'app_icon.ico'), '.'),
        (str(project_dir / 'logo.png'), '.'),
        (str(project_dir / 'packaging' / 'icons' / 'app_icon.icns'), '.'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'sounddevice',
        'woods_pack',
        'PIL',
        'PIL.Image',
        'PIL.ImageEnhance',
    ],
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
    name='GrooveTrainer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=str(project_dir / 'packaging' / 'macos' / 'entitlements.plist'),
    icon=str(project_dir / 'packaging' / 'icons' / 'app_icon.icns'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GrooveTrainer',
)
app = BUNDLE(
    coll,
    name='Groove Trainer.app',
    icon=str(project_dir / 'packaging' / 'icons' / 'app_icon.icns'),
    bundle_identifier='com.antonshcherbakov.groovetrainer',
    info_plist={
        'CFBundleDisplayName': 'Groove Trainer',
        'CFBundleName': 'Groove Trainer',
        'CFBundleShortVersionString': '1.0.1',
        'CFBundleVersion': '101',
        'CFBundleIconFile': 'app_icon.icns',
        'LSApplicationCategoryType': 'public.app-category.music',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'Copyright © Anton Shcherbakov',
    },
)
