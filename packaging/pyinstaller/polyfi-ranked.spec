from __future__ import annotations

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_root = Path(SPECPATH).parents[1]
src_root = project_root / 'src'
build_root = project_root / 'build' / 'windows'
icon_path = build_root / 'polyfi-ranked.ico'

sys.path.insert(0, str(src_root))

from wifi_pref_manager.icon_assets import write_app_icon_file


write_app_icon_file(icon_path)

hiddenimports = collect_submodules('pystray')
hiddenimports.append('PIL.ImageTk')
datas = collect_data_files('inspy_logger', includes=['version/VERSION.txt'])

a = Analysis(
    [str(src_root / 'wifi_pref_manager' / 'app.py')],
    pathex=[str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='polyfi-ranked',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='polyfi-ranked',
)
