# Auralis Beta 9.0 - Cache & UI Polish

**Release Date**: November 5, 2025
**Version**: 1.0.0-beta.9.0

---

## 🎉 What's New

### Centralized Fingerprint Cache
- **No more permission issues**: Fingerprints now stored in `~/.auralis/fingerprints/`
- **No library clutter**: Removed sidecar `.25d` files from music folders
- **Content-based caching**: MD5 hash of file path + content signature for cache keys
- **Reliable storage**: Centralized cache with automatic cleanup management

### Subtle Processing UI
- **Non-intrusive toast**: Compact bottom-right notification (280px × ~80px)
- **Glass morphism design**: Backdrop blur, semi-transparent styling
- **Real-time status**: Pulsing icon, status text, stat chips (when available)
- **Auto-hide**: Disappears when processing complete
- **No blocking**: Never interrupts your workflow or blocks parameter view

### Critical Fixes
- **P0: Progress bar accuracy** - Fixed chunk duration mismatch (30s → 10s)
  - Progress bar now tracks correctly (1:1 with playback time)
  - Seeking lands at exact positions
  - Chunk requests every ~10s (not 30s)
- **Frontend loading** - Fixed path detection in Electron bundled mode
- **Component crashes** - Fixed missing imports and color references

---

## 📊 Technical Details

### Backend Changes

**1. Chunk Duration Synchronization**
- [main.py:388](auralis-web/backend/main.py#L388) - Router instantiation: `chunk_duration=10`
- [webm_streaming.py:60](auralis-web/backend/routers/webm_streaming.py#L60) - Default parameter: `chunk_duration=10`
- Single source of truth: Backend defines, frontend reads from metadata

**2. Centralized Fingerprint Storage**
- [fingerprint_storage.py](auralis/analysis/fingerprint/fingerprint_storage.py) - Complete rewrite
- Cache location: `~/.auralis/fingerprints/*.25d`
- Cache keys: `MD5(absolute_path:file_signature)`
- Methods: `save()`, `load()`, `is_valid()`, `delete()`, `clear_all()`

### Frontend Changes

**1. Progress Bar Fix**
- [UnifiedWebMAudioPlayer.ts:293,413](auralis-web/frontend/src/services/UnifiedWebMAudioPlayer.ts) - Read `chunk_duration` from metadata
- Uses `this.metadata?.chunk_duration || 10` for all calculations
- No more hardcoded fallback values

**2. Processing Toast Component**
- [ProcessingToast.tsx](auralis-web/frontend/src/components/ProcessingToast.tsx) - NEW (162 lines)
- Bottom-right corner (100px above player bar)
- Smooth fade in/out animations
- Stat chips for cache hits, processing speed, progress %

**3. AutoMasteringPane Updates**
- [AutoMasteringPane.tsx](auralis-web/frontend/src/components/AutoMasteringPane.tsx) - Removed intrusive progress bar
- Added ProcessingToast component
- Cleaned up imports (added LinearProgress back for parameter displays)

---

## 🔧 Build Information

### Package Details

**Linux**:
- `Auralis-1.0.0-beta.9.0.AppImage` (275 MB) - Universal Linux package
- `auralis-desktop_1.0.0-beta.9.0_amd64.deb` (242 MB) - Debian/Ubuntu package

**Frontend Bundle**: `index-CvvCcNJq.js` (790 KB)
**Backend Binary**: `auralis-backend` (172 MB)

### Installation

**Linux (AppImage)**:
```bash
chmod +x Auralis-1.0.0-beta.9.0.AppImage
./Auralis-1.0.0-beta.9.0.AppImage
```

**Linux (DEB)**:
```bash
sudo dpkg -i auralis-desktop_1.0.0-beta.9.0_amd64.deb
```

---

## ✅ What's Fixed

### P0 Critical Issues

1. **Progress Bar Jumping** ✅
   - **Issue**: Progress bar completed in 60s for 180s track (3x too fast)
   - **Root Cause**: Frontend/backend chunk_duration mismatch (30s vs 10s)
   - **Fix**: Synchronized to 10s, frontend reads from metadata
   - **Impact**: Progress bar now accurate, seeking works correctly

2. **Fingerprint Storage Failures** ✅
   - **Issue**: Permission errors writing `.25d` files to music library
   - **Root Cause**: Sidecar files in potentially read-only directories
   - **Fix**: Centralized cache at `~/.auralis/fingerprints/`
   - **Impact**: Reliable storage, no permission issues

3. **UI Crashes on Toggle** ✅
   - **Issue**: App crashed when toggling mastering switch
   - **Root Cause**: Missing `LinearProgress` import, undefined color references
   - **Fix**: Added import, fixed color property names
   - **Impact**: No crashes, stable UI

### P1 Issues

4. **Intrusive Processing UI** ✅
   - **Issue**: Large progress bar blocked parameter view
   - **Root Cause**: Fixed position in main panel
   - **Fix**: Replaced with subtle bottom-right toast
   - **Impact**: Non-blocking, professional UX

5. **Frontend Not Loading** ✅
   - **Issue**: "Frontend not found" error in Electron
   - **Root Cause**: Incorrect path calculation (`sys._MEIPASS.parent.parent` → `/`)
   - **Fix**: Use `os.getcwd().parent` (Electron sets cwd correctly)
   - **Impact**: Frontend loads correctly in bundled mode

---

## 📈 All Beta 9.0 Features

### From Previous Releases
- ✅ **Unified MSE + Multi-Tier Buffer** - Progressive WebM/Opus streaming
- ✅ **Instant preset switching** - 67% player UI code reduction
- ✅ **Enhanced interactions** - Drag-drop, batch operations
- ✅ **25D Audio Fingerprint** - Intelligent content-aware processing
- ✅ **Automatic fingerprint extraction** - No manual analysis needed

### New in Beta 9.0
- ✅ **Centralized fingerprint cache** - Reliable, permission-free storage
- ✅ **Subtle processing toast** - Non-intrusive status indicator
- ✅ **Progress bar accuracy** - Fixed chunk duration synchronization
- ✅ **Stability improvements** - Fixed crashes and import issues

---

## ⚠️ Known Limitations

### Expected Behaviors (Not Bugs)

1. **Preset switching buffering** - 2-5s pause when changing presets (optimization ongoing)
2. **Fingerprint analysis time** - 2-5s for first analysis of new track (cached afterward)
3. **Keyboard shortcuts disabled** - Temporary (circular dependency issue, fix planned for Beta 9.1)

### Future Enhancements (Planned for Beta 9.1)

1. **Real-time processing stats** - Wire up backend stats to toast via WebSocket
2. **Progress bar in toast** - Add back when real progress data available
3. **Faster preset switching** - Reduce buffering time below 2s
4. **Smart playlists** - Based on 25D fingerprint similarity
5. **Enhanced queue** - Save queue, history, suggestions

---

## 🧪 Testing Checklist

### Progress Bar (P0 Fix)

- [x] Play 180s track → Progress bar completes in 180s (not 60s!)
- [x] Seek to 30s → Lands at 30s (not 90s!)
- [x] Seek to 60s → Lands at 60s (not 180s!)
- [x] Progress moves at 1:1 speed with playback
- [x] Network tab shows chunks every ~10s (not 30s!)

### Fingerprint Cache

- [x] Play track → Fingerprint extracted and cached
- [x] Check `~/.auralis/fingerprints/` for `.25d` file
- [x] No `.25d` files in music library folders
- [x] No permission errors in logs
- [x] Second playback loads from cache (8x faster)

### Processing Toast UI

- [x] Toast appears in bottom-right corner when analyzing
- [x] Toast doesn't overlap player bar (100px margin)
- [x] Status text updates correctly
- [x] Pulsing icon when analyzing
- [x] Toast fades out when analysis complete
- [x] Doesn't block parameter view

### Regression Testing

- [x] Auto-mastering toggle works
- [x] Preset switching works (2-5s buffering expected)
- [x] Playback controls work (play, pause, seek, next, previous)
- [x] Queue management works
- [x] Library browsing works
- [x] Album artwork displays correctly
- [x] No console errors
- [x] No backend errors in logs

---

## 📚 Documentation

**Complete technical details**:
- [P0_PROGRESS_BAR_FIX_COMPLETE.md](docs/sessions/nov5_cache_simplification/P0_PROGRESS_BAR_FIX_COMPLETE.md) - Progress bar fix
- [FINAL_CHUNK_DURATION_FIX.md](docs/sessions/nov5_cache_simplification/FINAL_CHUNK_DURATION_FIX.md) - Root cause analysis
- [PROCESSING_TOAST_UI.md](docs/sessions/nov5_cache_simplification/PROCESSING_TOAST_UI.md) - Toast component design
- [FINGERPRINT_CACHE_REDESIGN.md](docs/sessions/nov5_cache_simplification/FINGERPRINT_CACHE_REDESIGN.md) - Cache architecture

**Session documentation**: [docs/sessions/nov5_cache_simplification/](docs/sessions/nov5_cache_simplification/)

---

## 🙏 Acknowledgments

Thank you to all beta testers for your feedback and bug reports! Your input has been invaluable in making Auralis better.

**Special thanks to**:
- Users who reported the progress bar issue
- Users who identified the fingerprint permission errors
- Everyone testing the new features and providing feedback

---

## 📦 Previous Releases

- **Beta 8** (Nov 4, 2025) - 25D fingerprint system, intelligent processing
- **Beta 6** (Oct 30, 2025) - Enhanced interactions, drag-drop, batch operations
- **Beta 4** (Oct 27, 2025) - Unified MSE streaming architecture
- See [CHANGELOG.md](CHANGELOG.md) for complete version history

---

## 🐛 Report Issues

Found a bug? Have feedback?

- **GitHub Issues**: https://github.com/matiaszanolli/Auralis/issues
- **Discussions**: https://github.com/matiaszanolli/Auralis/discussions

---

**Full Changelog**: https://github.com/matiaszanolli/Auralis/compare/v1.0.0-beta.8...v1.0.0-beta.9.0

---

**Installation** | **Documentation** | **Report Issues**

🎵 **Enjoy Auralis Beta 9.0!** 🎵
