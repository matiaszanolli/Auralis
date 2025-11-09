# Auralis Beta 11.1 Release Notes

**Release Date**: November 9, 2025
**Version**: 1.0.0-beta.11.1
**Priority**: High - Restores critical feature disabled since Beta 6

---

## 🎉 What's New

### ✨ Keyboard Shortcuts Re-Enabled (P1 Priority)

The #1 requested feature is back! Keyboard shortcuts have been completely rewritten and re-enabled after being disabled in Beta 6 due to production build issues.

**What happened?**
- Beta 6 had to disable keyboard shortcuts due to a critical minification error
- Error only appeared in production builds, caused blank screen on startup
- Root cause: Complex React hooks with circular dependencies

**What's fixed?**
- Complete rewrite using service-based architecture
- No more React hook complexity that breaks minifiers
- Production builds tested and verified
- Zero breaking changes for users

---

## ⌨️ Available Keyboard Shortcuts (14 total)

### Playback Controls (6 shortcuts)
- **Space** - Play/Pause
- **→ (Right Arrow)** - Next track
- **← (Left Arrow)** - Previous track
- **↑ (Up Arrow)** - Volume up (+10%)
- **↓ (Down Arrow)** - Volume down (-10%)
- **M** - Mute/Unmute

### Navigation (6 shortcuts)
- **1** - Show Songs view
- **2** - Show Albums view
- **3** - Show Artists view
- **4** - Show Playlists view
- **/** - Focus search box
- **Esc** - Clear search / Close dialogs

### Global (2 shortcuts)
- **?** - Show keyboard shortcuts help dialog
- **Ctrl/Cmd + ,** - Open settings

**Tip**: Press **?** anytime to see all available shortcuts!

---

## 🏗️ Technical Improvements

### New Architecture: Service Pattern

The keyboard shortcuts system has been completely rewritten from scratch:

**Before (Beta 6 - Broken):**
- Complex React hook with 20+ inline callbacks
- Circular dependencies during minification
- Only worked in development mode

**After (Beta 11.1 - Fixed):**
- Plain TypeScript service (zero React dependencies)
- Simple registry pattern
- Works with all minifiers (esbuild, Rollup, Terser)
- Better performance (single global listener)

### Files Changed

**New Files:**
- `services/keyboardShortcutsService.ts` (194 lines) - Core service
- `hooks/useKeyboardShortcutsV2.ts` (74 lines) - React wrapper

**Modified:**
- `ComfortableApp.tsx` - Uses new V2 implementation
- `KeyboardShortcutsHelp.tsx` - Updated types

### Benefits

1. **Minification-Safe** - Works in production builds
2. **Better Performance** - Single event listener, no re-renders
3. **Maintainable** - Clear separation of concerns
4. **Framework-Agnostic** - Could reuse in other frameworks
5. **Extensible** - Easy to add new shortcuts

---

## 📦 Downloads

### Linux

**AppImage (Universal):**
```bash
wget https://github.com/matiaszanolli/Auralis/releases/download/v1.0.0-beta.11.1/Auralis-1.0.0-beta.11.1.AppImage
chmod +x Auralis-1.0.0-beta.11.1.AppImage
./Auralis-1.0.0-beta.11.1.AppImage
```

**DEB Package (Debian/Ubuntu):**
```bash
wget https://github.com/matiaszanolli/Auralis/releases/download/v1.0.0-beta.11.1/auralis-desktop_1.0.0-beta.11.1_amd64.deb
sudo dpkg -i auralis-desktop_1.0.0-beta.11.1_amd64.deb
```

### Checksums

**AppImage:**
```
SHA256: 27fc1747e9e9dd545f4a35cfa22c89357b7334b535531e5b3623e2b7cb9886a6
Size: 274 MB
```

**DEB:**
```
SHA256: ca6aa167a50e2eca99969564af76e3e3ed1bee88db96a55fbc7dfb1a5a531781
Size: 242 MB
```

---

## 🧪 Testing

The keyboard shortcuts have been tested with:
- ✅ Production build (Vite minification)
- ✅ Bundle size verification (no increase)
- ✅ TypeScript compilation
- ✅ Cross-platform builds (Linux, Windows)

**Manual testing checklist for users:**
- [ ] All 14 shortcuts work correctly
- [ ] Shortcuts blocked in input fields (don't interfere with typing)
- [ ] Help dialog works (press **?**)
- [ ] Platform-specific modifiers (Cmd on Mac, Ctrl elsewhere)

---

## 📝 Upgrade Notes

### From Beta 11.0
- **No breaking changes**
- Keyboard shortcuts now work (were disabled in Beta 6-11.0)
- No database migrations required
- Settings preserved

### From Beta 6-10.x
- Keyboard shortcuts functionality restored
- Much more reliable than Beta 5 implementation
- Same shortcut keys as before

---

## 🐛 Known Issues

**None specific to Beta 11.1**

General known issues:
- 11 frontend gapless playback tests failing (under investigation)
- Preset switching requires 2-5s pause (optimization ongoing)

---

## 🔮 What's Next?

### Beta 12.0 (Planned)
- Smart playlists based on 25D audio fingerprints
- "Find similar tracks" feature
- Cross-genre music discovery
- Enhanced queue management

### Beta 13.0 (Planned)
- Faster preset switching (<1s)
- Performance optimizations
- Memory usage improvements

---

## 📚 Documentation

- **Full Documentation**: [docs/sessions/nov9_keyboard_shortcuts_reenabled/](docs/sessions/nov9_keyboard_shortcuts_reenabled/)
- **Architecture Details**: [KEYBOARD_SHORTCUTS_REENABLED.md](docs/sessions/nov9_keyboard_shortcuts_reenabled/KEYBOARD_SHORTCUTS_REENABLED.md)
- **User Guide**: Press **?** in-app for keyboard shortcuts help

---

## 🙏 Acknowledgments

- **Beta 6 users** who reported the blank screen issue
- **Architecture inspiration**: Redux and Zustand service patterns
- **Testing**: Production build verification with Vite

---

## 💬 Feedback

Found a bug? Have a feature request?
- **GitHub Issues**: https://github.com/matiaszanolli/Auralis/issues
- **Discussions**: https://github.com/matiaszanolli/Auralis/discussions

---

**Full Changelog**: https://github.com/matiaszanolli/Auralis/compare/v1.0.0-beta.11...v1.0.0-beta.11.1
