# AppImage Streaming Fix

## Problem

The AppImage builds successfully but **audio streaming doesn't work**. The application starts, but when you try to play enhanced audio, the streaming fails silently.

## Root Cause

The **Rust DSP module** (`libauralis_dsp.so`) was not being included in the PyInstaller-packaged backend binary.

### Why This Matters

The Rust DSP module provides critical audio processing functionality:
- **Audio fingerprinting** (25D analysis)
- **HPSS** (Harmonic/Percussive Source Separation)
- **YIN** pitch detection
- **Chroma** analysis
- **Tempo** detection

Without this module, the backend can start but cannot process audio for streaming.

### What Was Wrong

In `auralis-web/backend/auralis-backend.spec`:
```python
binaries = []  # ❌ Empty - Rust module not included
```

The Rust module lives in `vendor/auralis-dsp/target/release/libauralis_dsp.so`, which is **outside** the standard Python package structure, so PyInstaller's `collect_all()` doesn't automatically find it.

## Solution

Updated the spec file to explicitly include the Rust DSP module:

```python
# Include Rust DSP module (.so file)
rust_dsp_path = '../../vendor/auralis-dsp/target/release'
rust_dsp_files = glob.glob(os.path.join(rust_dsp_path, 'libauralis_dsp.so*'))
if not rust_dsp_files:
    print("WARNING: Rust DSP module not found! Build it with: cd vendor/auralis-dsp && maturin build --release")
binaries = [(so_file, '.') for so_file in rust_dsp_files]
```

## How to Rebuild AppImage

### 1. Build Rust DSP Module
```bash
cd vendor/auralis-dsp
maturin build --release
cd ../..
```

Verify it's built:
```bash
ls -lh vendor/auralis-dsp/target/release/libauralis_dsp.so
# Should show: -rwxrwxr-x ... 3.0M ... libauralis_dsp.so
```

### 2. Build AppImage
```bash
# Full build (includes tests)
python build_auralis.py

# Fast build (skip tests)
python build_auralis.py --skip-tests
```

The AppImage will be in `dist/`:
```bash
ls -lh dist/*.AppImage
```

### 3. Test the Fix

Run the AppImage and test streaming:
```bash
chmod +x dist/Auralis-*.AppImage
./dist/Auralis-*.AppImage
```

1. Add some music to your library
2. Click on a track to play it
3. Toggle "Enhanced" playback mode
4. **Streaming should now work** - you'll see processing messages and hear the enhanced audio

### 4. Verify Rust Module is Included

Extract the AppImage and check:
```bash
./dist/Auralis-*.AppImage --appimage-extract
ls -lh squashfs-root/resources/backend/_internal/libauralis_dsp.so*
```

You should see the 3MB .so file.

## Technical Details

### PyInstaller Packaging

The Electron app uses PyInstaller to bundle the Python backend into a standalone executable (`auralis-backend`).

**Key paths:**
- **Development**: Backend runs from `auralis-web/backend/main.py` with system Python
- **Production**: Backend runs from `resources/backend/auralis-backend` (PyInstaller bundle)

### Rust Module Loading

Python loads the Rust module via:
```python
from auralis_dsp import compute_fingerprint
```

PyO3 (Rust↔Python bindings) requires the `.so` file to be:
1. In the same directory as the Python executable, OR
2. On the `PYTHONPATH`, OR
3. In the `_internal/` directory for PyInstaller bundles

Our fix puts it in the root of the bundle (`.`), which PyInstaller automatically moves to `_internal/`.

## Build Script Changes Needed

The main build script (`build_auralis.py`) should be updated to:

1. **Check** if Rust module is built before packaging
2. **Build** Rust module if missing
3. **Verify** the module is included in the final package

Example addition to `build_auralis.py`:
```python
def ensure_rust_module_built():
    """Ensure Rust DSP module is built before packaging"""
    rust_module = Path("vendor/auralis-dsp/target/release/libauralis_dsp.so")

    if not rust_module.exists():
        print("⚠️  Rust DSP module not found. Building...")
        subprocess.run(
            ["maturin", "build", "--release"],
            cwd="vendor/auralis-dsp",
            check=True
        )
        print("✓ Rust DSP module built")
    else:
        print("✓ Rust DSP module found")
```

## Commit Reference

Fix committed in: `f0c3a8b7 - fix(build): Include Rust DSP module in PyInstaller builds`

## Related Files

- `auralis-web/backend/auralis-backend.spec` - PyInstaller spec (fixed)
- `desktop/main.js` - Electron backend launcher
- `desktop/package.json` - Electron Builder config
- `vendor/auralis-dsp/` - Rust DSP source
- `build_auralis.py` - Main build script (needs update)
