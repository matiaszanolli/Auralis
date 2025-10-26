# Build History - Auralis Desktop

This document consolidates the build milestone history for the Auralis desktop application.

---

## Latest Build: Alpha 1 (October 25, 2025)

**Version**: 1.0.0-alpha.1
**Status**: ✅ Complete
**Platform**: Linux (AppImage + DEB)

### Build Artifacts
- `Auralis-1.0.0-alpha.1.AppImage` (250 MB)
- `auralis-desktop_1.0.0-alpha.1_amd64.deb` (178 MB)

### Key Features
- Real-time audio enhancement with stateful processing
- Multi-tier buffer system with predictive caching
- Library management for large collections (10k+ tracks)
- Modern UI with design system
- 100% local processing (no cloud)

### Critical Fixes
- **Audio fuzz/noise fix**: Maintained compressor state across chunks
- **Electron window fix**: Works on Linux/Wayland
- **Gain pumping fix**: Stateful compression prevents artifacts

**Documentation**: See `BUILD_OCT25_AUDIO_FIX.md` and `docs/sessions/oct25_alpha1_release/`

---

## Previous Builds

### Electron Build Fix (October 2024)

**Issue**: Electron build packaging was broken
**Fix**: Updated electron-builder configuration and packaging scripts
**Result**: Working AppImage and DEB packages

**Key Changes**:
- Fixed Python backend bundling with PyInstaller
- Fixed frontend build integration
- Fixed IPC communication between Electron and Python
- Added proper error handling for missing backend

### First Working Build (September 2024)

**Milestone**: First successful desktop application build
**Platform**: Linux
**Status**: Proof of concept

**Features**:
- Basic Electron wrapper
- Python backend integration
- React frontend loading
- Native folder picker (IPC)

---

## Build Process

### Current Build Process (v1.0.0-alpha.1)

```bash
# 1. Build frontend
cd auralis-web/frontend
npm run build
# Output: build/ directory (741 KB gzipped: 221 KB)

# 2. Build backend
cd auralis-web/backend
pyinstaller auralis-backend.spec --clean -y
# Output: dist/auralis-backend/ (standalone executable)

# 3. Build desktop application
cd desktop
npm run build:linux
# Output: ../dist/Auralis-1.0.0-alpha.1.AppImage
#         ../dist/auralis-desktop_1.0.0-alpha.1_amd64.deb
```

### Build Requirements
- Node.js >= 16.0.0
- Python >= 3.8.0
- Electron >= 27.0.0
- electron-builder >= 24.6.4
- PyInstaller >= 5.0.0

---

## Build Configuration

### electron-builder Config
- **appId**: com.auralis.desktop
- **productName**: Auralis
- **Linux targets**: AppImage, DEB
- **Windows targets**: NSIS
- **macOS targets**: DMG

### PyInstaller Config
- **Entry point**: `auralis-web/backend/main.py`
- **Includes**: All Auralis modules, FastAPI, dependencies
- **Exclusions**: Tests, dev dependencies
- **Output**: Single directory with executable

---

## Known Build Issues

### Fixed Issues
- ✅ AppImage startup error (port conflicts)
- ✅ Blank Electron window (IPC errors)
- ✅ Backend not found (packaging paths)
- ✅ Window not showing on Wayland (Electron flags)

### Current Issues
- None reported

---

## Critical Fixes Applied Over Time

### October 25, 2025
- Fixed audio fuzz/noise (stateful processing)
- Fixed Electron window on Wayland
- Fixed gain pumping artifacts

### October 24, 2024
- Fixed RMS boost overdrive
- Fixed dynamics expansion behavior
- Added library scan API

### September 2024
- Fixed WebSocket connection issues
- Fixed native folder picker IPC
- Fixed backend startup race conditions

---

## Testing Builds

### AppImage Testing
```bash
# Make executable
chmod +x dist/Auralis-1.0.0-alpha.1.AppImage

# Run from terminal (see logs)
./dist/Auralis-1.0.0-alpha.1.AppImage

# Check if backend port is free
lsof -ti:8765 | xargs kill -9
```

### DEB Package Testing
```bash
# Install
sudo dpkg -i dist/auralis-desktop_1.0.0-alpha.1_amd64.deb

# Fix dependencies if needed
sudo apt-get install -f

# Run
auralis-desktop
```

---

## Build Scripts

### Development Build
```bash
npm run dev                 # From root or desktop/
```

### Production Build
```bash
npm run package             # Current platform
npm run package:linux       # Linux (.AppImage, .deb)
npm run package:win         # Windows
npm run package:mac         # macOS
```

---

## Build Size Analysis

### AppImage (250 MB)
- Python backend: ~180 MB
- Frontend assets: ~10 MB
- Electron runtime: ~60 MB

### DEB Package (178 MB)
- Compressed AppImage contents
- Debian package metadata
- Desktop integration files

### Optimization Opportunities
- Reduce Python dependencies (exclude dev packages)
- Optimize frontend bundle (tree-shaking)
- Use UPX compression for binaries
- Split optional dependencies

---

## Release Process

See `docs/versions/RELEASE_GUIDE.md` for complete release process.

Quick summary:
1. Bump version: `python scripts/sync_version.py X.Y.Z`
2. Update CHANGELOG.md
3. Build all platforms
4. Test on each platform
5. Create GitHub release
6. Upload artifacts
7. Publish release notes

---

This document consolidates build history from:
- `CRITICAL_FIXES_APPLIED.md`
- `ELECTRON_BUILD_FIXED.md`
- `BUILD_COMPLETE.md`
- `BUILD_SUMMARY.md`
