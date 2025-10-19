# Native OS Folder Picker Added

**Date:** October 14, 2025
**Status:** ✅ Complete - Ready to Test

---

## What's New

Added **native OS folder picker** for library management - no more typing file paths!

### Before (Manual Path Entry):
```
Click "Scan Folder" → Type: /home/user/Music → Hope you typed it right
```

### After (Native Picker):
```
Click "Scan Folder" → Native OS dialog opens → Browse visually → Select folder → Done!
```

---

## How It Works

### In Electron App (Desktop)
Uses **native OS folder picker dialog**:
- **macOS:** Standard macOS folder picker
- **Windows:** Standard Windows folder browser
- **Linux:** Standard GTK/KDE file picker

**User experience:**
1. Click "📁 Scan Folder" button
2. Native folder picker opens
3. Browse your folders visually
4. Click "Select Folder" or "Open"
5. Scan starts automatically

### In Web Browser
Falls back to **prompt dialog**:
- Browser can't access native file system
- Shows text prompt for path entry
- Same as before (manual input)

**User experience:**
1. Click "📁 Scan Folder" button
2. Prompt dialog appears
3. Type folder path manually
4. Click OK
5. Scan starts

---

## Technical Implementation

### Detection Logic

```typescript
// Check if running in Electron
const isElectron = () => {
  return !!(window as any).electronAPI;
};
```

**How it works:**
- Electron apps have `window.electronAPI` exposed
- Web browsers don't have this API
- Automatically chooses appropriate method

### Electron Path

```typescript
// Use native folder picker in Electron
if (isElectron()) {
  const result = await window.electronAPI.selectFolder();
  if (result && result.length > 0) {
    folderPath = result[0];
  } else {
    return; // User cancelled
  }
}
```

**What happens:**
1. Calls Electron IPC handler `select-folder`
2. Main process shows native dialog
3. Returns array of selected paths
4. Uses first path (single folder selection)
5. If empty array, user cancelled

### Web Browser Fallback

```typescript
else {
  // Fallback to prompt in web browser
  folderPath = prompt('Enter folder path to scan:\n(e.g., /home/user/Music)') || undefined;
  if (!folderPath) return;
}
```

**Why needed:**
- Web browsers can't show native file pickers for security
- Can't access arbitrary file system paths
- Only works with user-initiated file input elements
- Prompt is simplest fallback

---

## Electron IPC Setup

### Already Configured ✅

**Main Process** (`desktop/main.js` lines 314-319):
```javascript
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(auralisApp.mainWindow, {
    properties: ['openDirectory']
  });
  return result.filePaths;
});
```

**Preload Script** (`desktop/preload.js` line 7):
```javascript
contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  // ...
});
```

**Result:** Frontend can safely call `window.electronAPI.selectFolder()`

---

## Files Modified

### CozyLibraryView.tsx

**Added:**
- `isElectron()` helper function (lines 91-94)
- Native folder picker logic (lines 100-113)
- Web browser fallback (lines 115-118)

**Changed:**
- `handleScanFolder()` function now has smart detection
- No more direct `prompt()` call in Electron

**Lines changed:** ~30 lines modified

---

## Testing

### Test in Electron App

1. **Build and start Electron:**
   ```bash
   cd /mnt/data/src/matchering/desktop
   npm run dev
   ```

2. **Click "Scan Folder" button** (📁 blue folder icon)

3. **Verify native dialog opens:**
   - macOS: macOS-style folder picker
   - Windows: Windows Explorer folder picker
   - Linux: GTK/KDE file browser

4. **Browse to music folder**

5. **Click "Select Folder" / "Open"**

6. **Verify scan starts automatically**

7. **Check console** for: `Loaded X tracks from library`

### Test in Web Browser

1. **Start web interface:**
   ```bash
   python launch-auralis-web.py
   ```

2. **Open browser:** `http://localhost:8000`

3. **Click "Scan Folder" button**

4. **Verify text prompt appears** (fallback mode)

5. **Type folder path** (e.g., `/home/user/Music`)

6. **Click OK**

7. **Verify scan starts**

---

## User Experience Comparison

### Electron App (Native Picker) ⭐

**Pros:**
- ✅ Visual folder browsing
- ✅ No typos or path errors
- ✅ Standard OS interface (familiar)
- ✅ Can see folder contents
- ✅ Bookmarks and shortcuts work
- ✅ Auto-completion
- ✅ Multiple drives visible

**Cons:**
- ❌ Requires Electron (desktop app)

### Web Browser (Prompt Fallback)

**Pros:**
- ✅ Works in any browser
- ✅ No installation needed
- ✅ Simple implementation

**Cons:**
- ❌ Must type full path
- ❌ Easy to make typos
- ❌ No visual browsing
- ❌ Must remember exact path
- ❌ Case-sensitive
- ❌ No autocomplete

---

## Future Enhancements

### Drag-and-Drop

**Add to CozyLibraryView:**
```typescript
const handleDrop = async (event: React.DragEvent) => {
  event.preventDefault();
  const files = event.dataTransfer.files;

  // Check if folder was dropped
  if (files.length > 0 && files[0].type === '') {
    // It's a folder
    const folderPath = files[0].path;
    // Scan the folder
    scanFolder(folderPath);
  }
};
```

**Benefits:**
- Even faster than clicking button
- Modern UX
- Works in both Electron and web

### Recent Folders

**Add state:**
```typescript
const [recentFolders, setRecentFolders] = useState<string[]>([]);

// After successful scan:
setRecentFolders(prev => [folderPath, ...prev.slice(0, 4)]);

// Show dropdown:
<Menu>
  {recentFolders.map(folder => (
    <MenuItem onClick={() => scanFolder(folder)}>
      {folder}
    </MenuItem>
  ))}
</Menu>
```

**Benefits:**
- Quick re-scan
- No re-browsing needed
- Better UX

### Auto-Detect Music Folders

**Common locations:**
```typescript
const musicFolders = [
  '~/Music',
  '~/Music/iTunes/iTunes Media/Music',
  '~/Music/Spotify',
  'C:\\Users\\{username}\\Music',
  'C:\\Users\\{username}\\My Music',
  '/home/{username}/Music'
];

// Check which exist
const existingFolders = await Promise.all(
  musicFolders.map(async folder => {
    const exists = await checkFolderExists(folder);
    return exists ? folder : null;
  })
);

// Suggest to user
if (existingFolders.some(f => f !== null)) {
  showSuggestions(existingFolders.filter(f => f !== null));
}
```

**Benefits:**
- One-click setup
- No searching needed
- Smart defaults

### Web File System Access API

**For modern browsers:**
```typescript
// Chrome/Edge support native folder picker!
if ('showDirectoryPicker' in window) {
  const dirHandle = await window.showDirectoryPicker();
  // Can access files without path strings
}
```

**Benefits:**
- Native picker in web browsers
- No Electron required
- Modern web standard
- Works in Chrome, Edge, Opera

**Limitations:**
- Not in Firefox or Safari yet
- Requires HTTPS
- User must grant permission

---

## Comparison with Other Apps

### iTunes / Apple Music
- ✅ Has native folder picker
- ✅ Can add multiple folders
- ✅ Watches folders for changes
- ❌ macOS only

**Auralis equivalent:** ✅ Native picker in Electron

### Spotify Desktop
- ❌ No folder management (streaming only)
- ✅ Can import local files
- ✅ Native folder picker

**Auralis equivalent:** ✅ Native picker + full library management

### VLC Media Player
- ✅ Native folder picker
- ✅ Recursive scan
- ✅ Drag-and-drop
- ✅ Recent folders

**Auralis equivalent:** ✅ Native picker, ⏳ Drag-drop (future)

### foobar2000
- ✅ Advanced folder management
- ✅ Multiple library locations
- ✅ Monitor folders
- ✅ Native picker

**Auralis equivalent:** ✅ Native picker, ⏳ Advanced features (future)

---

## Summary

**Before:**
- ❌ Manual path typing
- ❌ Error-prone
- ❌ Frustrating UX

**After:**
- ✅ Native OS folder picker (Electron)
- ✅ Visual folder browsing
- ✅ No typos or errors
- ✅ Fallback for web browser
- ✅ Professional UX

**Bundle Size:** No change (uses existing Electron IPC)

**Next:** Test in Electron app to verify native picker works!

---

## Quick Test

```bash
# Start Electron app
cd /mnt/data/src/matchering/desktop
npm run dev

# When app opens:
# 1. Click Scan Folder (📁) button
# 2. Native folder picker should appear
# 3. Browse to your music folder
# 4. Click Select/Open
# 5. Watch scan complete
```

**Expected:** Native OS dialog opens (not text prompt!)

---

**Status:** 🟢 **NATIVE FOLDER PICKER READY**
**Platform:** Electron (desktop app)
**Fallback:** Text prompt (web browser)
**User Impact:** Much better UX!
