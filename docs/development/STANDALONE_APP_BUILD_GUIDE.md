# Standalone App Build Guide

## 🎯 Overview

This guide explains how to build Auralis as a standalone desktop application using **Electron** + **Python** + **React**. The final app bundles everything into a single distributable that users can install without needing Python, Node.js, or any other dependencies.

## 🏗️ Architecture

```
Standalone Auralis App
├── Electron Shell (JavaScript)
│   ├── Creates native window
│   ├── Spawns Python backend
│   └── Loads React frontend
├── Python Backend (Bundled with PyInstaller)
│   ├── FastAPI server
│   ├── Audio processing engine
│   └── All Python dependencies
└── React Frontend (Built static files)
    ├── Material-UI components
    ├── Processing interface
    └── All JavaScript/CSS assets
```

## 📋 Prerequisites

### Required Software
- **Node.js 16+** - JavaScript runtime
- **Python 3.8+** - Python interpreter
- **PyInstaller** - Python app bundler (`pip install pyinstaller`)
- **npm/yarn** - Package manager

### Required Packages
```bash
# Install Python dependencies
pip install -r requirements.txt
pip install pyinstaller

# Install Node.js dependencies
npm run install:all
# Or manually:
cd desktop && npm install
cd ../auralis-web/frontend && npm install
```

## 🚀 Quick Start

### Option 1: One-Command Build (Recommended)
```bash
# Build everything and package for your current platform
npm run package

# Or for specific platforms:
npm run package:win     # Windows
npm run package:mac     # macOS
npm run package:linux   # Linux
```

### Option 2: Step-by-Step Build
```bash
# Step 1: Build frontend and backend
npm run build

# Step 2: Package with Electron
npm run package
```

## 📝 Detailed Build Process

### Step 1: Build React Frontend

```bash
cd auralis-web/frontend
npm install
npm run build
```

This creates `auralis-web/frontend/build/` with:
- Optimized JavaScript bundles
- Minified CSS
- Static assets (images, fonts)
- index.html entry point

### Step 2: Bundle Python Backend

```bash
cd auralis-web/backend

# Create PyInstaller spec (first time only)
# This is automated by build.js

# Bundle backend
pyinstaller --clean --noconfirm auralis-backend.spec
```

This creates `auralis-web/backend/dist/auralis-backend/` with:
- Standalone executable
- All Python dependencies
- Auralis processing engine
- FastAPI server

**PyInstaller Configuration Highlights:**
- **One-folder mode** - All files in a directory
- **Console enabled** - Shows backend logs (disable for production)
- **All dependencies included** - numpy, scipy, soundfile, fastapi, etc.
- **Hidden imports** - Explicit inclusion of dynamic imports
- **Optimized size** - Excludes matplotlib, tkinter, Qt

### Step 3: Package with Electron

```bash
cd desktop
npm install
npm run build  # or build:win / build:mac / build:linux
```

This creates `dist/` with platform-specific installers:
- **Windows**: `.exe` installer (NSIS) + portable .exe
- **macOS**: `.dmg` disk image + `.app` bundle
- **Linux**: `.AppImage` + `.deb` package

**Electron Builder Configuration Highlights:**
- Includes `desktop/main.js` and `preload.js`
- Copies frontend build to `resources/frontend`
- Copies backend dist to `resources/backend`
- Code signing support (configure in package.json)
- Auto-updater support built-in

## 📦 Build Scripts

### `scripts/build.js`

Comprehensive build automation:

```javascript
const BuildManager = require('./scripts/build.js');
const builder = new BuildManager();
builder.build();
```

**Features:**
- ✅ Checks requirements (Node, Python, PyInstaller)
- ✅ Cleans previous builds
- ✅ Builds React frontend
- ✅ Bundles Python backend with PyInstaller
- ✅ Prepares Electron resources
- ✅ Detailed logging at each step

### `scripts/package.js`

Electron packaging automation:

```javascript
const PackageManager = require('./scripts/package.js');
const packager = new PackageManager();
packager.package();
```

**Features:**
- ✅ Checks if build exists (runs build if needed)
- ✅ Installs Electron dependencies
- ✅ Packages for specified platform(s)
- ✅ Shows output files and sizes
- ✅ Platform-specific optimizations

## 🎨 Electron Configuration

### Development vs Production

**Development Mode** (`npm run dev`):
- Runs `python auralis-web/backend/main.py` directly
- Loads frontend from `http://localhost:3000` (React dev server)
- Hot reload enabled
- DevTools open automatically

**Production Mode** (`npm run package`):
- Runs bundled `auralis-backend.exe` from resources
- Loads frontend from `http://localhost:8000` (backend serves static files)
- No hot reload
- DevTools disabled

### Platform-Specific Notes

#### Windows
- Creates NSIS installer with custom wizard
- Supports installation directory selection
- Creates desktop and start menu shortcuts
- Includes uninstaller
- Requires code signing for SmartScreen bypass

#### macOS
- Creates DMG with drag-to-Applications
- Universal binary (x64 + ARM64)
- Requires code signing and notarization
- Gatekeeper entitlements included
- Native look and feel

#### Linux
- AppImage for universal compatibility
- DEB package for Debian/Ubuntu
- Desktop entry for application menu
- Icon support
- No code signing required

## 🔧 Customization

### App Metadata

Edit `desktop/package.json`:

```json
{
  "name": "auralis-desktop",
  "version": "1.0.0",
  "description": "Auralis Audio Mastering Desktop Application",
  "author": "Auralis Team",
  "build": {
    "appId": "com.auralis.desktop",
    "productName": "Auralis",
    "copyright": "Copyright © 2024 Auralis Team"
  }
}
```

### Window Settings

Edit `desktop/main.js`:

```javascript
this.mainWindow = new BrowserWindow({
  width: 1400,
  height: 900,
  minWidth: 800,
  minHeight: 600,
  // ... more options
});
```

### Backend Bundling

Edit `auralis-web/backend/auralis-backend.spec`:

```python
# Add more hidden imports
hiddenimports=[
    'your_module_here',
    # ...
],

# Exclude unnecessary packages
excludes=[
    'matplotlib',
    'tkinter',
    # ...
]
```

## 📊 Build Output

### File Sizes (Approximate)

| Platform | Installer Size | Unpacked Size |
|----------|---------------|---------------|
| Windows  | ~200 MB       | ~400 MB       |
| macOS    | ~180 MB       | ~350 MB       |
| Linux    | ~190 MB       | ~380 MB       |

**Size Breakdown:**
- Python backend: ~150 MB (numpy, scipy, ML models)
- Electron runtime: ~80 MB
- React frontend: ~2 MB (minified)
- Audio libraries: ~50 MB (soundfile, resampy)
- Other dependencies: ~100 MB

### Optimization Tips

1. **Exclude unused Python packages:**
   ```python
   excludes=['matplotlib', 'tkinter', 'PyQt5', 'jupyter']
   ```

2. **Use UPX compression:**
   ```python
   upx=True,  # Compress executables
   ```

3. **Tree shaking for frontend:**
   - Already enabled by React Scripts
   - Use dynamic imports for large components

4. **Platform-specific builds:**
   - Don't bundle unnecessary platform binaries
   - Target specific architectures

## 🧪 Testing

### Local Testing (Before Building)

```bash
# Test frontend
cd auralis-web/frontend
npm start
# Visit http://localhost:3000

# Test backend
cd auralis-web/backend
python main.py
# Visit http://localhost:8000/api/docs

# Test Electron (dev mode)
npm run dev
```

### Testing Built App

```bash
# After building
npm run package

# Install the created package:
# Windows: dist/Auralis Setup 1.0.0.exe
# macOS: dist/Auralis-1.0.0.dmg
# Linux: dist/Auralis-1.0.0.AppImage

# Or run the unpacked app:
# Windows: dist/win-unpacked/Auralis.exe
# macOS: dist/mac/Auralis.app
# Linux: dist/linux-unpacked/auralis
```

### Debugging Production Builds

Enable console in production:

```javascript
// desktop/main.js
this.mainWindow = new BrowserWindow({
  webPreferences: {
    devTools: true  // Enable DevTools in production
  }
});

// Open DevTools on startup
this.mainWindow.webContents.openDevTools();
```

Check backend logs:
- Electron shows backend stdout/stderr in console
- Backend runs with `PYTHONUNBUFFERED=1` for immediate output

## 🚨 Common Issues

### Issue: PyInstaller Missing Modules

**Symptom:** App crashes with "ModuleNotFoundError"

**Solution:** Add to hidden imports in `.spec` file:
```python
hiddenimports=[
    'missing_module_name',
]
```

### Issue: Backend Timeout on Startup

**Symptom:** "Backend startup timeout" error

**Solutions:**
1. Increase timeout in `main.js` (from 30s to 60s)
2. Check if antivirus is blocking the backend executable
3. Run backend manually to see errors:
   ```bash
   ./dist/win-unpacked/resources/backend/auralis-backend.exe
   ```

### Issue: Frontend Not Loading

**Symptom:** White screen or error page

**Solutions:**
1. Check if backend is serving static files
2. Verify frontend build exists in resources
3. Check browser console for errors (F12)
4. Try loading `http://localhost:8000` directly

### Issue: Large File Size

**Solutions:**
1. Enable UPX compression
2. Exclude unnecessary packages
3. Use `--onefile` mode (slower startup but smaller)
4. Split into multiple platforms instead of universal

### Issue: Code Signing Required (macOS)

**Symptom:** "App is damaged and can't be opened"

**Solutions:**
1. Sign the app: `codesign --force --deep --sign - Auralis.app`
2. Remove quarantine: `xattr -cr Auralis.app`
3. Or: System Preferences → Security → "Open Anyway"

For distribution, use Apple Developer certificate:
```json
"mac": {
  "identity": "Developer ID Application: Your Name (TEAM_ID)"
}
```

## 📚 Advanced Topics

### Auto-Updates

Electron Builder includes auto-updater:

```javascript
const { autoUpdater } = require('electron-updater');

autoUpdater.checkForUpdatesAndNotify();
```

Configure in `package.json`:
```json
"publish": {
  "provider": "github",
  "owner": "matiaszanolli",
  "repo": "Auralis"
}
```

### Code Signing

**Windows:**
```bash
# Get a code signing certificate
# Then configure in package.json:
"win": {
  "certificateFile": "path/to/cert.pfx",
  "certificatePassword": "..."
}
```

**macOS:**
```bash
# Requires Apple Developer account
"mac": {
  "identity": "Developer ID Application: ...",
  "hardenedRuntime": true,
  "entitlements": "entitlements.plist"
}

# Notarize after signing
xcrun notarytool submit ...
```

### Custom Installer

**NSIS (Windows):**
Create `build/installer.nsh`:
```nsis
!macro customInstall
  ; Custom installation steps
!macroend
```

**DMG (macOS):**
Customize background image, window size in `package.json`

## 🎯 CI/CD Integration

### GitHub Actions Example

`.github/workflows/build.yml`:
```yaml
name: Build Auralis

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [windows-latest, macos-latest, ubuntu-latest]

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '16'

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller
          npm run install:all

      - name: Build app
        run: npm run package

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: auralis-${{ matrix.os }}
          path: dist/*
```

## 🎉 Summary

**Build Commands:**
```bash
npm run build        # Build frontend + backend
npm run package      # Create distributable app
npm run package:win  # Windows-specific build
npm run package:mac  # macOS-specific build
npm run package:linux # Linux-specific build
```

**Output:**
- `dist/` - Contains platform installers
- Ready to distribute to users
- No dependencies required for end users

**Next Steps:**
1. Test the built app thoroughly
2. Set up code signing (optional but recommended)
3. Configure auto-updates (optional)
4. Create release notes
5. Distribute to users!

---

**The standalone app build system is production-ready!** 🚀

Just run `npm run package` and you'll have a distributable desktop app.