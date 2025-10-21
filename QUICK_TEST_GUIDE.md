# Quick Testing Guide - Phase 1 Features

**5-Minute Quick Test** - Test all 4 Phase 1 features

---

## 🚀 Start Application

```bash
cd /mnt/data/src/matchering
python launch-auralis-web.py

# Open browser: http://localhost:8765
```

---

## ✅ 1-Minute Tests

### ❤️ Favorites (30 seconds)
1. Click heart icon on a track → Should turn pink
2. Click "Favourites" in sidebar → Track should appear
3. Click heart again → Track disappears
4. **✅ PASS**: Hearts toggle, favorites persist

---

### 📋 Playlists (1 minute)
1. Click "+ Create Playlist" in sidebar
2. Name: "Test", Description: "Testing"
3. Click Create → Playlist appears in sidebar
4. Hover and click trash icon → Confirm delete
5. **✅ PASS**: Create and delete work

---

### 🎨 Album Art (1 minute)
1. Check library grid → Should see album artwork or placeholder icons
2. Play a track → Check player bar shows artwork thumbnail (64x64px)
3. Switch tracks → Artwork updates
4. **✅ PASS**: Artwork displays in grid and player

---

### 🎵 Queue (1 minute)
1. Play multiple tracks → Queue appears below grid
2. Drag a track to reorder → Smooth animation
3. Hover track → Click X to remove
4. Click "Shuffle" button → Queue randomizes
5. **✅ PASS**: All queue operations work

---

## 🐛 What to Look For

**Good Signs** ✅:
- Toast notifications appear for all actions
- No errors in browser console (F12)
- Changes persist after page refresh
- Smooth animations, no lag

**Bad Signs** ❌:
- Console errors (red text in F12 → Console)
- Features don't work after refresh
- Slow or laggy UI
- Missing toast notifications

---

## 📞 Report Issues

If you find problems:
1. Open browser console (F12)
2. Screenshot any errors
3. Note exact steps to reproduce
4. Share with development team

---

**Full Testing Guide**: See [PHASE1_TESTING_PLAN.md](PHASE1_TESTING_PLAN.md)
