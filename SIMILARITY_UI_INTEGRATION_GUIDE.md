# Similarity System - UI Integration Guide

**Target File**: `auralis-web/frontend/src/components/CozyLibraryView.tsx`
**Estimated Time**: 1-2 hours
**Components Ready**: ✅ SimilarTracks, ✅ SimilarityVisualization

---

## 🎯 Integration Steps

### Step 1: Import SimilarTracks Component

Add to imports section (top of file):

```typescript
import SimilarTracks from './SimilarTracks';
```

### Step 2: Add Sidebar Layout

Modify the main return statement to add a sidebar for similar tracks. The structure should be:

```
┌───────────────────────────────────────────┬──────────────┐
│         Main Content Area                 │  Similar     │
│         (existing tracks/albums)          │  Tracks      │
│                                           │  Sidebar     │
│                                           │  (280px)     │
└───────────────────────────────────────────┴──────────────┘
```

**Code to add** (around line 550-650, in the main return section):

```typescript
return (
  <Box sx={{ display: 'flex', gap: 2 }}>
    {/* Main Content - Existing Container */}
    <Box sx={{ flex: 1 }}>
      <Container maxWidth="xl" sx={{ py: 4 }}>
        {/* ALL EXISTING CONTENT STAYS HERE */}
        {/* ... existing header ... */}
        {/* ... existing search bar ... */}
        {/* ... existing grid/list view ... */}
      </Container>
    </Box>

    {/* Similar Tracks Sidebar - NEW */}
    <Box
      sx={{
        width: 280,
        borderLeft: '1px solid rgba(255, 255, 255, 0.1)',
        backgroundColor: 'rgba(10, 14, 39, 0.8)',
        height: '100vh',
        position: 'sticky',
        top: 0,
        overflowY: 'auto'
      }}
    >
      <SimilarTracks
        trackId={currentTrackId || null}
        onTrackSelect={(trackId) => {
          // Find and play the selected track
          const track = tracks.find(t => t.id === trackId);
          if (track && onTrackPlay) {
            onTrackPlay(track);
          }
        }}
        limit={5}
        useGraph={true}
      />
    </Box>
  </Box>
);
```

### Step 3: Add Context Menu "Find Similar"

Find the TrackRow component usage (around line 650-700) and add context menu option:

**Current structure** (example):
```typescript
<TrackRow
  track={track}
  onPlay={() => handlePlayTrack(track)}
  // ... other props
/>
```

**Add contextMenuOptions prop**:
```typescript
<TrackRow
  track={track}
  onPlay={() => handlePlayTrack(track)}
  contextMenuOptions={[
    {
      label: 'Find Similar',
      icon: <AutoAwesome />, // Import from @mui/icons-material
      onClick: () => {
        // Scroll similar tracks into view
        setCurrentTrackId(track.id);
        // Optional: highlight sidebar
      }
    },
    // ... existing options (Add to Queue, Edit Metadata, etc.)
  ]}
/>
```

**Required import**:
```typescript
import { AutoAwesome } from '@mui/icons-material';
```

### Step 4: Ensure Current Track State Updates

Make sure `currentTrackId` updates when a track plays. This should already exist in `handlePlayTrack`:

```typescript
const handlePlayTrack = async (track: Track) => {
  setCurrentTrackId(track.id); // ← Ensure this line exists
  setIsPlaying(true);

  if (onTrackPlay) {
    await onTrackPlay(track);
  }
  // ... rest of function
};
```

### Step 5: Handle Empty States

The SimilarTracks component already handles:
- ✅ No track selected (shows "Play a track to discover similar music")
- ✅ No similar tracks found
- ✅ Loading state
- ✅ Error state

No additional code needed!

---

## 🎨 Styling Notes

The SimilarTracks component uses the Auralis design system:
- Dark theme: `#0A0E27` background
- Aurora gradient: `#667eea → #764ba2`
- Similarity badges color-coded:
  - 90%+ = turquoise (`#00d4aa`)
  - 80-90% = purple (`#667eea`)
  - 70-80% = dark purple (`#764ba2`)
  - <70% = gray (`#8b92b0`)

It will match the existing UI perfectly!

---

## 🧪 Testing the Integration

### Test Case 1: Basic Functionality
1. Start the app: `npm run dev`
2. Open browser to `http://localhost:3000`
3. Play any track
4. **Expected**: Similar tracks appear in right sidebar
5. Click on a similar track
6. **Expected**: That track starts playing

### Test Case 2: Empty States
1. Don't play any track
2. **Expected**: Sidebar shows "Play a track to discover similar music"
3. Play a track with no fingerprint
4. **Expected**: Sidebar shows "No similar tracks found"

### Test Case 3: Loading State
1. Play a track
2. **Expected**: Brief loading spinner, then results

### Test Case 4: Context Menu
1. Right-click on a track in the list
2. Click "Find Similar"
3. **Expected**: Sidebar updates with similar tracks for that track

---

## 🔧 Troubleshooting

### Issue: "Module not found: SimilarTracks"
**Solution**: Ensure the component file exists at:
```
auralis-web/frontend/src/components/SimilarTracks.tsx
```

### Issue: "similarityService is not defined"
**Solution**: The SimilarTracks component imports it automatically. If you see this error, check:
```
auralis-web/frontend/src/services/similarityService.ts
```

### Issue: Backend returns 404
**Solution**: Ensure backend is running and similarity router is registered:
```python
# In auralis-web/backend/main.py
from routers.similarity import create_similarity_router

# Should have this line:
app.include_router(
    create_similarity_router(
        get_library_manager=lambda: library_manager,
        get_similarity_system=lambda: similarity_system,
        get_graph_builder=lambda: graph_builder
    )
)
```

### Issue: No similar tracks showing
**Possible causes**:
1. No fingerprints extracted yet
   - **Solution**: Run fingerprint extraction (see deployment guide)
2. Similarity system not fitted
   - **Solution**: POST to `/api/similarity/fit`
3. Graph not built (if using `useGraph=true`)
   - **Solution**: POST to `/api/similarity/graph/build`

---

## 📊 Advanced Integration (Optional)

### Add Similarity Visualization Dialog

For detailed track comparison, add a comparison dialog:

```typescript
import SimilarityVisualization from './SimilarityVisualization';
import { Dialog, DialogTitle, DialogContent } from '@mui/material';

// Add state
const [compareDialogOpen, setCompareDialogOpen] = useState(false);
const [compareTrackIds, setCompareTrackIds] = useState<[number, number] | null>(null);

// Add to context menu
{
  label: 'Compare with Current Track',
  icon: <Compare />,
  onClick: () => {
    if (currentTrackId) {
      setCompareTrackIds([currentTrackId, track.id]);
      setCompareDialogOpen(true);
    }
  },
  disabled: !currentTrackId
}

// Add dialog to render
<Dialog
  open={compareDialogOpen}
  onClose={() => setCompareDialogOpen(false)}
  maxWidth="md"
  fullWidth
>
  <DialogTitle>Track Similarity Analysis</DialogTitle>
  <DialogContent>
    {compareTrackIds && (
      <SimilarityVisualization
        trackId1={compareTrackIds[0]}
        trackId2={compareTrackIds[1]}
        topN={5}
      />
    )}
  </DialogContent>
</Dialog>
```

### Add Graph Build UI (Settings Panel)

In settings/preferences panel:

```typescript
import { CircularProgress, Button, Alert } from '@mui/material';

// Add state
const [buildingGraph, setBuildingGraph] = useState(false);
const [graphStats, setGraphStats] = useState(null);

// Add UI
<Box>
  <Typography variant="h6">Similarity Graph</Typography>
  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
    Pre-compute similarity for faster queries
  </Typography>

  {graphStats && (
    <Alert severity="info" sx={{ mb: 2 }}>
      Graph built: {graphStats.total_edges} edges for {graphStats.total_tracks} tracks
      <br />
      Average distance: {graphStats.avg_distance.toFixed(4)}
    </Alert>
  )}

  <Button
    variant="contained"
    onClick={async () => {
      setBuildingGraph(true);
      try {
        const response = await fetch(
          'http://localhost:8765/api/similarity/graph/build?k=10',
          { method: 'POST' }
        );
        const stats = await response.json();
        setGraphStats(stats);
      } catch (err) {
        console.error('Failed to build graph:', err);
      } finally {
        setBuildingGraph(false);
      }
    }}
    disabled={buildingGraph}
  >
    {buildingGraph ? <CircularProgress size={24} /> : 'Build Similarity Graph'}
  </Button>
</Box>
```

---

## 🚀 Deployment Checklist

Before deploying with UI integration:

- [ ] SimilarTracks component integrated
- [ ] Context menu "Find Similar" added
- [ ] Current track state wired up
- [ ] Tested with real tracks
- [ ] Backend API endpoints working
- [ ] Fingerprints extracted for library
- [ ] Similarity system fitted
- [ ] K-NN graph built (optional but recommended)

---

## 📝 Code Summary

**Files to modify**: 1
- `auralis-web/frontend/src/components/CozyLibraryView.tsx`

**Lines to add**: ~50-70 lines

**Components used**: 2
- `SimilarTracks` (already created)
- `SimilarityVisualization` (optional, for advanced comparison)

**Estimated time**: 1-2 hours

---

## 🎯 Result

After integration, users will be able to:
1. ✅ See similar tracks automatically when playing music
2. ✅ Click similar tracks to play them
3. ✅ Right-click tracks to find similar ones
4. ✅ Compare tracks in detail (if visualization added)
5. ✅ Discover music based on acoustic similarity

The similarity system will be **fully integrated** and provide immediate value!

---

**Need help?** Check the component documentation:
- [SimilarTracks.tsx](auralis-web/frontend/src/components/SimilarTracks.tsx)
- [SimilarityVisualization.tsx](auralis-web/frontend/src/components/SimilarityVisualization.tsx)
- [similarityService.ts](auralis-web/frontend/src/services/similarityService.ts)
