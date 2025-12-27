# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
import glob

datas = [
    ('../../auralis', 'auralis'),
    # Backend modules (config, routers) - CRITICAL for WebSocket endpoint!
    ('config', 'config'),
    ('routers', 'routers'),
    ('cache', 'cache'),
    ('services', 'services'),
]

# Rust DSP module will be collected automatically via collect_all('auralis_dsp')
# No need to manually add binaries - maturin develop installs it as a Python package
binaries = []

hiddenimports = [
    'auralis.analysis.fingerprint.fingerprint_storage',
    'auralis.analysis.fingerprint',
    # Rust DSP module (CRITICAL - required for audio processing!)
    'auralis_dsp',
    # Backend modules (CRITICAL - WebSocket endpoint won't work without these!)
    'config',
    'config.app',
    'config.globals',
    'config.middleware',
    'config.routes',
    'config.startup',
    'routers',
    'routers.system',
    'routers.library',
    'routers.player',
    'routers.enhancement',
    'routers.albums',
    'routers.artists',
    'routers.artwork',
    'routers.files',
    'routers.metadata',
    'routers.playlists',
    'routers.similarity',
    'routers.cache_streamlined',
    'audio_stream_controller',
    'chunked_processor',
    'processing_engine',
    'processing_api',
    'fingerprint_generator',
    'player_state',
    'proactive_buffer',
    'streamlined_worker',
    'helpers',
    'schemas',
    'state_manager',
    'metrics_collector',
    'analysis_extractor',
    'audio_content_predictor',
    'learning_system',
    'self_tuner',
    'track_analysis_cache',
    'memory_monitor',
    'cache',
    'cache.manager',
    'services',
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
    # GPU/CUDA packages (WE DON'T USE GPU!)
    'cupy',
    'cupy_backends',
    'cupy.cuda',
    'cuda',
    'cudnn',
    'numba',
    'numba.cuda',
    'llvmlite',
    'llvmlite.binding',
    # Scientific packages not used
    'matplotlib',
    'matplotlib.pyplot',
    'pandas',
    'sklearn',
    'scikit-learn',
    # Testing frameworks
    'pytest',
    '_pytest',
    'hypothesis',
    'mock',
    # Image processing
    'PIL',
    'Pillow',
    # Type checking
    'mypy',
    # GUI frameworks
    'tkinter',
    '_tkinter',
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
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

# Filter out CUDA/GPU binaries
def filter_binaries(all_binaries):
    """Remove CUDA and GPU-related binaries"""
    excluded_patterns = [
        'libcu',      # CUDA libraries (libcublas, libcufft, etc.)
        'libnv',      # NVIDIA libraries (libnvrtc, libnccl, etc.)
        'cudnn',      # cuDNN
        'cudart',     # CUDA runtime
    ]
    filtered = []
    for binary in all_binaries:
        # Binary format is (source, dest) tuple
        source = binary[0] if len(binary) > 0 else ''
        # Check if binary matches any excluded pattern
        if not any(pattern in source.lower() for pattern in excluded_patterns):
            filtered.append(binary)
        else:
            print(f"EXCLUDING GPU BINARY: {source}")
    return filtered
# Collect auralis module
tmp_ret = collect_all('auralis')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Collect Rust DSP module (auralis_dsp) - critical for audio processing!
tmp_ret = collect_all('auralis_dsp')
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

# Filter out CUDA binaries AFTER Analysis (this catches ALL binaries)
print("\n" + "="*80)
print("FILTERING CUDA/GPU BINARIES")
print("="*80)
original_count = len(a.binaries)
a.binaries = filter_binaries(a.binaries)
removed_count = original_count - len(a.binaries)
print(f"Removed {removed_count} GPU binaries from {original_count} total")
print("="*80 + "\n")

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
