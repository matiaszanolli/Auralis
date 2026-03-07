# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Auralis backend
Bundles the FastAPI server + Rust DSP + auralis core into a standalone executable
"""
import os
import sys
import glob
import site

# Find Rust DSP module from site-packages (installed via maturin/pip)
dsp_binaries = []
for sp in site.getsitepackages() + [site.getusersitepackages()]:
    dsp_dir = os.path.join(sp, 'auralis_dsp')
    if os.path.isdir(dsp_dir):
        for f in os.listdir(dsp_dir):
            full = os.path.join(dsp_dir, f)
            if f.endswith('.so') or f.endswith('.pyd'):
                dsp_binaries.append((full, 'auralis_dsp'))
            elif f == '__init__.py':
                dsp_binaries.append((full, 'auralis_dsp'))
        break

# Fallback: check target/release for the raw .so
if not dsp_binaries:
    rust_path = os.path.join('vendor', 'auralis-dsp', 'target', 'release')
    for so in glob.glob(os.path.join(rust_path, 'libauralis_dsp*.so')):
        dsp_binaries.append((so, '.'))

if not dsp_binaries:
    print("WARNING: Rust DSP module not found! Build with: cd vendor/auralis-dsp && maturin build --release && pip install target/wheels/*.whl")

a = Analysis(
    ['auralis-web/backend/main.py'],
    pathex=['.'],
    binaries=dsp_binaries,
    datas=[
        ('auralis', 'auralis'),
        ('auralis-web/backend/*.py', 'auralis-web/backend'),
        ('auralis-web/backend/config', 'auralis-web/backend/config'),
        ('auralis-web/backend/core', 'auralis-web/backend/core'),
        ('auralis-web/backend/routers', 'auralis-web/backend/routers'),
        ('auralis-web/backend/services', 'auralis-web/backend/services'),
        ('auralis-web/backend/websocket', 'auralis-web/backend/websocket'),
        ('auralis-web/backend/analysis', 'auralis-web/backend/analysis'),
        ('auralis-web/backend/cache', 'auralis-web/backend/cache'),
        ('auralis-web/backend/encoding', 'auralis-web/backend/encoding'),
        ('auralis-web/backend/monitoring', 'auralis-web/backend/monitoring'),
        ('auralis-web/backend/security', 'auralis-web/backend/security'),
        ('auralis-web/backend/desktop', 'auralis-web/backend/desktop'),
    ],
    hiddenimports=[
        # Auralis core
        'auralis',
        'auralis.core',
        'auralis.core.hybrid_processor',
        'auralis.core.simple_mastering',
        'auralis.core.processor',
        'auralis.core.config',
        'auralis.core.recording_type_detector',
        'auralis.dsp',
        'auralis.dsp.unified',
        'auralis.dsp.psychoacoustic_eq',
        'auralis.dsp.advanced_dynamics',
        'auralis.dsp.realtime_adaptive_eq',
        'auralis.io',
        'auralis.io.unified_loader',
        'auralis.io.results',
        'auralis.analysis',
        'auralis.learning',
        'auralis.optimization',
        'auralis.library',
        'auralis.library.manager',
        'auralis.player',
        'auralis.services',
        'auralis.utils',
        # Rust DSP
        'auralis_dsp',
        # FastAPI / Uvicorn
        'uvicorn',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.http.httptools_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'fastapi',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'pydantic',
        'pydantic.deprecated',
        'pydantic.deprecated.decorator',
        'starlette',
        'starlette.responses',
        'starlette.websockets',
        # Audio / Scientific
        'numpy',
        'scipy',
        'scipy.signal',
        'scipy.fft',
        'soundfile',
        'librosa',
        'resampy',
        'numba',
        'mutagen',
        # Database
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'aiosqlite',
        # Async / HTTP
        'aiohttp',
        'aiofiles',
        'psutil',
        'multipart',
        'python_multipart',
        # Backend modules
        'processing_engine',
        'chunked_processor',
        'audio_stream_controller',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'IPython',
        'jupyter',
        'cupy',
        'cupy_backends',
        'cuda',
        'pandas',
        'sklearn',
        'scikit-learn',
        'asyncpg',
        'test',
        'tests',
        'pytest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='auralis-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='auralis-backend',
)
