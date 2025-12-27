# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
import glob

datas = [('../../auralis', 'auralis')]

# Include Rust DSP module (.so file)
rust_dsp_path = '../../vendor/auralis-dsp/target/release'
rust_dsp_files = glob.glob(os.path.join(rust_dsp_path, 'libauralis_dsp.so*'))
if not rust_dsp_files:
    print("WARNING: Rust DSP module not found! Build it with: cd vendor/auralis-dsp && maturin build --release")
binaries = [(so_file, '.') for so_file in rust_dsp_files]

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

# Exclude unnecessary packages to reduce binary size
excludes = [
    # Scientific packages not used
    'matplotlib',
    'matplotlib.pyplot',
    'pandas',
    'sklearn',
    'cupy',
    # Testing frameworks
    'pytest',
    '_pytest',
    # Image processing
    'PIL',
    'Pillow',
    # Type checking
    'mypy',
    # GUI frameworks
    'tkinter',
    '_tkinter',
    # Build tools
    'setuptools',
    'wheel',
    'pip',
    # Unused backend packages
    'alembic',
    'asyncpg',
    'redis',
    'jose',
    'passlib',
    'email_validator',
    'statsmodels',
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
    excludes=excludes,
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
