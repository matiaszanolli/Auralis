# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('../../auralis', 'auralis')]
binaries = []
hiddenimports = [
    'auralis.analysis.fingerprint.fingerprint_storage',
    'auralis.analysis.fingerprint',
    # Database dependencies
    'sqlalchemy',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.orm',
    'sqlalchemy.pool',
    'sqlalchemy.dialects.sqlite',
    # Audio file handling
    'mutagen',
    'mutagen.mp3',
    'mutagen.flac',
    'mutagen.oggvorbis',
    'mutagen.mp4',
    'mutagen.wave',
    # Scientific computing
    'scipy',
    'scipy.signal',
    'scipy.fft',
    'numpy',
    'soundfile',
    'librosa',
    # FastAPI dependencies
    'fastapi',
    'uvicorn',
    'pydantic',
    'starlette',
]
tmp_ret = collect_all('auralis')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
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
    a.binaries,
    a.datas,
    [],
    name='auralis-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
