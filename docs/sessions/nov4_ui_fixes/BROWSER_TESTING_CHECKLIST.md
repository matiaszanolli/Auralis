# Browser Testing Checklist - November 4, 2025

**Server URLs**:
- Backend: http://127.0.0.1:8765
- Frontend: http://localhost:3001
- API Docs: http://127.0.0.1:8765/api/docs

---

## Test 1: Album Card Collapse Fix ✅

**Navigate to**: http://localhost:3001 → Albums view

**Test Steps**:
1. Open Albums view from sidebar
2. Scroll through album grid
3. Look for albums without artwork (show gradient fallback)
4. Verify all cards maintain 160x160px square dimensions
5. Check grid alignment is perfect

**Expected Results**:
- ✅ All album cards same size (1:1 aspect ratio)
- ✅ No collapsed or thin cards
- ✅ Gradient fallback visible for albums without artwork
- ✅ Grid alignment perfect

**Status**: ⏳ Pending

---

## Test 2: Infinite Scroll Scrollbar Fix ✅

**Navigate to**: Albums, Artists, or Songs view

**Test Steps**:
1. Open a view with many items (Albums or Songs)
2. Observe scrollbar thumb size
3. Should be small if library is large (e.g., 1000+ items)
4. Scroll through list
5. Verify scrollbar position feels accurate

**Expected Results**:
- ✅ Scrollbar thumb represents full library size
- ✅ Thumb is proportionally small for large libraries
- ✅ Scrollbar position accurate as you scroll

**Test with**:
- Albums view (if 100+ albums, thumb should be ~10% of track)
- Songs view (if 1000+ tracks, thumb should be tiny)

**Status**: ⏳ Pending

---

## Test 3: Sidebar Navigation from Detail Views ✅

**Navigate to**: Any album or artist detail

**Test Steps**:
1. Click on an album to view details
2. While in album detail, click "Albums" in sidebar
3. Should return to albums list (not stuck)
4. Click on an artist to view details
5. While in artist detail, click "Artists" in sidebar
6. Should return to artists list
7. Repeat with "Songs" button

**Expected Results**:
- ✅ Sidebar buttons always work
- ✅ Can navigate from detail views to list views
- ✅ View resets properly (no cached state)
- ⚠️ Brief flash as component remounts (expected)

**Status**: ⏳ Pending

---

## Test 4: Auto-Mastering Visualizer UI ✅

**Navigate to**: http://localhost:3001 → Main player view

**Test Steps**:
1. Locate "Auto-Mastering" pane on right side
2. Verify pane renders correctly
3. Toggle auto-mastering ON
4. Observe UI sections:
   - Audio Characteristics (3 progress bars)
   - Applied Processing (parameter list)
   - Info box

**Expected Results**:
- ✅ Pane visible on right side (320px wide on desktop)
- ✅ Toggle switch works
- ✅ When OFF: Shows "disabled" message
- ✅ When ON: Shows all sections
- ✅ Progress bars with color gradients
- ✅ Chips showing labels (Dark/Balanced/Bright, etc.)

**Visual Check**:
- Purple-violet gradient for spectral balance
- Blue-violet for dynamic range
- Teal-blue for energy level
- Clean Material-UI styling

**Status**: ⏳ Pending

---

## Test 5: Real Data Integration ✅

**Navigate to**: http://localhost:3001 → Play a track

**Test Steps**:
1. Enable auto-mastering in visualizer pane
2. Play a track from your library
3. Wait for track to process (~2-4 seconds)
4. Observe visualizer updating
5. Check if values change from defaults (0.5/0.5/0.5)
6. Open browser console (F12) → Network tab
7. Look for `/api/processing/parameters` requests
8. Verify requests every ~2 seconds

**Expected Results**:
- ✅ Initial values: Defaults or mock data
- ✅ After track processes: Real values appear
- ✅ Values change based on track characteristics
- ✅ Network shows polling every 2 seconds
- ✅ Response contains all 10 fields

**Example Real Values**:
```json
{
  "spectral_balance": 0.65,  // Not exactly 0.5
  "dynamic_range": 0.72,
  "energy_level": 0.58,
  "target_lufs": -14.0,
  "peak_target_db": -1.0,
  "bass_boost": 0.8,
  "air_boost": 1.2,
  "compression_amount": 0.35,
  "expansion_amount": 0.0,
  "stereo_width": 0.75
}
```

**Debug Steps** (if showing defaults):
1. Check console for errors
2. Verify track is playing
3. Check `/api/processing/parameters` response
4. Verify enhancement is enabled

**Status**: ⏳ Pending

---

## Test 6: Processing Parameters API ✅

**Navigate to**: http://127.0.0.1:8765/api/docs

**Test Steps**:
1. Open Swagger UI
2. Find `/api/processing/parameters` endpoint
3. Click "Try it out" → "Execute"
4. Verify response structure
5. Test multiple times
6. Verify consistent field structure

**Expected Results**:
- ✅ Endpoint documented in Swagger
- ✅ GET request works (200 OK)
- ✅ All 10 fields present
- ✅ Field types correct (floats)
- ✅ Value ranges valid

**Status**: ⏳ Pending

---

## Test 7: Component Remount Behavior ✅

**Test for**: Sidebar navigation fix

**Test Steps**:
1. Navigate to Albums list
2. Scroll down to position 50
3. Click on an album to view details
4. Click "Albums" in sidebar
5. Observe scroll position

**Expected Results**:
- ⚠️ Scroll position resets to top (expected - component remount)
- ✅ Navigation works correctly
- ✅ No errors in console

**Note**: Brief scroll position loss is expected and acceptable (intentional remount).

**Status**: ⏳ Pending

---

## Known Issues / Expected Behavior

### 1. Visualizer Shows Defaults Initially
**Expected**: Visualizer shows default values (0.5/0.5/0.5) until a track is processed
**When**: First launch or before playing any track
**Resolution**: Play a track with enhancement enabled

### 2. Component Remount Flash
**Expected**: Brief flash when navigating from detail views
**Why**: Component remounts to reset state (intentional)
**Impact**: Negligible, only on navigation

### 3. Virtual Spacer Height Approximate
**Expected**: Scrollbar may not be pixel-perfect accurate
**Why**: Using estimated heights (280px/row, 88px/row)
**Impact**: Negligible, scrollbar doesn't need exact precision

---

## Success Criteria

All 7 tests pass:
- ✅ Album cards maintain aspect ratio
- ✅ Scrollbars represent full library
- ✅ Sidebar navigation always works
- ✅ Visualizer UI renders correctly
- ✅ Real data appears in visualizer
- ✅ API endpoint works
- ✅ Component remount behavior acceptable

---

## Debugging Tools

### Browser Console
```javascript
// Check if processing parameters are being fetched
fetch('http://127.0.0.1:8765/api/processing/parameters')
  .then(r => r.json())
  .then(console.log)

// Check enhancement settings
fetch('http://127.0.0.1:8765/api/player/enhancement/status')
  .then(r => r.json())
  .then(console.log)
```

### Network Tab
- Filter: `/api/processing/parameters`
- Should see requests every ~2 seconds when enhancement enabled
- Check response payload for real vs default values

### React DevTools
- Inspect AutoMasteringPane component
- Check state updates (params state)
- Verify polling interval

---

## Report Template

**Test Results** (fill in after testing):

1. Album Card Collapse: [ ] Pass [ ] Fail
2. Infinite Scroll Scrollbar: [ ] Pass [ ] Fail
3. Sidebar Navigation: [ ] Pass [ ] Fail
4. Auto-Mastering Visualizer UI: [ ] Pass [ ] Fail
5. Real Data Integration: [ ] Pass [ ] Fail
6. API Endpoint: [ ] Pass [ ] Fail
7. Component Remount: [ ] Pass [ ] Fail

**Issues Found**:
- (List any issues here)

**Screenshots**:
- (Attach screenshots if needed)

---

**Testing Status**: Ready to begin
**Server Running**: ✅ Backend (8765) + Frontend (3001)
**Tester**: Please verify all 7 test cases
