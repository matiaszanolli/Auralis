# Build Quick Reference

## 🚀 Quick Commands

```bash
# Development
npm run dev                    # Run app in dev mode (hot reload)

# Building
npm run build                  # Build frontend + backend
npm run package                # Create standalone app for current platform
npm run package:win            # Windows installer (.exe)
npm run package:mac            # macOS disk image (.dmg)
npm run package:linux          # Linux AppImage + deb

# Testing
python -m pytest tests/ -v     # Run Python tests
npm test                       # Run JavaScript tests (if configured)

# Cleaning
npm run clean                  # Remove all build artifacts
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `scripts/build.js` | Builds React frontend + bundles Python backend |
| `scripts/package.js` | Creates Electron distributable |
| `desktop/main.js` | Electron main process (window management) |
| `desktop/package.json` | Electron Builder configuration |
| `auralis-web/backend/auralis-backend.spec` | PyInstaller configuration |

## 🛠️ Build Requirements

- **Node.js 24+** (for Electron and React)
- **Python 3.14+** (for audio processing)
- **PyInstaller** (`pip install pyinstaller`)
- **~500MB free disk space** (for builds)

## 📦 Build Output

```
dist/
├── Auralis-1.0.0.dmg              # macOS installer
├── Auralis Setup 1.0.0.exe        # Windows installer
├── Auralis-1.0.0.AppImage         # Linux portable
└── auralis_1.0.0_amd64.deb        # Linux Debian package
```

## 🐛 Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| "PyInstaller not found" | `pip install pyinstaller` |
| "Backend startup timeout" | Increase timeout in `desktop/main.js` line 77 |
| "White screen" | Check backend is running: visit http://localhost:8000 |
| "Module not found" | Add to hiddenimports in `auralis-backend.spec` |
| Large file size | Enable UPX compression in `.spec` file |

## 🔄 Build Workflow

```
1. npm run build
   ├─> Builds React (auralis-web/frontend/build/)
   └─> Bundles Python (auralis-web/backend/dist/)

2. npm run package
   ├─> Copies builds to desktop/resources/
   ├─> Runs electron-builder
   └─> Creates installer in dist/
```

## ⚡ Performance Notes

| Platform | Build Time | Installer Size |
|----------|------------|----------------|
| Windows  | ~5 mins    | ~200 MB        |
| macOS    | ~6 mins    | ~180 MB        |
| Linux    | ~4 mins    | ~190 MB        |

## 🎯 Platform-Specific Notes

### Windows
- Creates NSIS installer with wizard
- Portable .exe also generated
- Requires code signing to avoid SmartScreen warnings

### macOS
- Creates .dmg with drag-to-Applications
- Requires code signing and notarization for Gatekeeper
- Use `codesign --force --deep --sign - Auralis.app` for local testing

### Linux
- AppImage works on all distros (no installation)
- DEB for Debian/Ubuntu systems
- No code signing required

## 📝 Before Releasing

- [ ] Test on target platform
- [ ] Update version in `desktop/package.json`
- [ ] Create release notes
- [ ] Sign app (Windows/macOS)
- [ ] Test installation
- [ ] Test uninstallation
- [ ] Test auto-updater (if configured)

## 🆘 Need Help?

- **Full guide**: STANDALONE_APP_BUILD_GUIDE.md — removed in a docs cleanup (`408b632a`); no longer in the repo
- **Architecture**: [CLAUDE.md](../../CLAUDE.md)
- **Processing UI**: AUDIO_PROCESSING_UI_IMPLEMENTATION.md — removed in a docs cleanup (`ccb6d87b`); no longer in the repo
- **Issues**: GitHub Issues

---

**TL;DR:** Run `npm run package` and you get a distributable app!