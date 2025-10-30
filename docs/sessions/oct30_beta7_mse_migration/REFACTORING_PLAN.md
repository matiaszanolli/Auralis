# BottomPlayerBarConnected.tsx Refactoring Plan

**Date**: October 30, 2025
**Goal**: Modularize 970-line component for MSE integration
**Strategy**: Extract logical sections into separate hooks and components

---

## 📊 **Current Structure Analysis**

### File Stats
- **Total lines**: 970
- **Main responsibilities**:
  1. Audio playback management (HTML5 audio)
  2. Gapless playback & crossfade
  3. Stream URL management
  4. Volume control
  5. Favorite/love tracking
  6. Progress bar UI
  7. Player controls UI

### Identified Sections

1. **Audio Playback Logic** (Lines ~192-283)
   - Stream URL generation
   - Audio element management
   - Playback state synchronization
   - Volume control

2. **Gapless Playback** (Lines ~293-450)
   - Next track detection
   - Pre-loading logic
   - Crossfade management
   - Audio element switching

3. **Player Controls** (Lines ~500-700)
   - Play/pause button
   - Skip next/previous
   - Volume slider
   - Progress bar

4. **Track Info Display** (Lines ~700-850)
   - Album art
   - Track title/artist
   - Favorite button

5. **Audio Elements** (Lines ~871-960)
   - Main audio element
   - Next audio element (gapless)
   - Event handlers

---

## 🎯 **Refactoring Strategy**

### Phase 1: Extract Audio Playback Hook
**New file**: `hooks/useAudioPlayback.ts`

**Responsibilities**:
- Audio element refs management
- Stream URL generation
- MSE vs HTML5 mode switching
- Playback state synchronization

**Interface**:
```typescript
interface UseAudioPlaybackReturn {
  audioRef: RefObject<HTMLAudioElement>;
  nextAudioRef: RefObject<HTMLAudioElement>;
  isBuffering: boolean;
  loadTrack: (trackId: number, preset: string, intensity: number) => void;
  switchPreset: (preset: string, intensity: number) => void;
}
```

**Extracted code**: ~150 lines

---

### Phase 2: Extract Gapless Playback Hook
**New file**: `hooks/useGaplessPlayback.ts`

**Responsibilities**:
- Next track detection
- Pre-loading logic
- Crossfade timing
- Audio element switching

**Interface**:
```typescript
interface UseGaplessPlaybackReturn {
  gaplessEnabled: boolean;
  crossfadeEnabled: boolean;
  crossfadeDuration: number;
  nextTrack: Track | null;
  preloadNextTrack: () => void;
}
```

**Extracted code**: ~100 lines

---

### Phase 3: Extract Player Controls Component
**New file**: `components/player/PlayerControls.tsx`

**Responsibilities**:
- Play/pause button
- Skip buttons
- Volume slider
- Enhancement toggle

**Props**:
```typescript
interface PlayerControlsProps {
  isPlaying: boolean;
  volume: number;
  onPlayPause: () => void;
  onNext: () => void;
  onPrevious: () => void;
  onVolumeChange: (volume: number) => void;
  enhancementEnabled: boolean;
  onEnhancementToggle: (enabled: boolean) => void;
}
```

**Extracted code**: ~150 lines

---

### Phase 4: Extract Track Info Component
**New file**: `components/player/TrackInfo.tsx`

**Responsibilities**:
- Album art display
- Track title/artist
- Favorite button
- Lyrics button

**Props**:
```typescript
interface TrackInfoProps {
  track: Track | null;
  isLoved: boolean;
  onToggleLove: () => void;
  onToggleLyrics?: () => void;
}
```

**Extracted code**: ~80 lines

---

### Phase 5: Extract Progress Bar Component
**New file**: `components/player/ProgressBar.tsx`

**Responsibilities**:
- Progress display
- Time display
- Seek functionality

**Props**:
```typescript
interface ProgressBarProps {
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
}
```

**Extracted code**: ~60 lines

---

## 📁 **New File Structure**

```
auralis-web/frontend/src/
├── hooks/
│   ├── useAudioPlayback.ts          ✨ NEW - Audio playback logic
│   ├── useGaplessPlayback.ts        ✨ NEW - Gapless/crossfade logic
│   ├── useMSEController.ts          ✅ DONE - MSE management
│   └── usePlayerAPI.ts              ✅ EXISTS - Backend API
│
├── components/
│   ├── player/
│   │   ├── PlayerControls.tsx       ✨ NEW - Play/pause/skip/volume
│   │   ├── TrackInfo.tsx            ✨ NEW - Album art/title/favorite
│   │   ├── ProgressBar.tsx          ✨ NEW - Progress bar/seek
│   │   └── AudioElements.tsx        ✨ NEW - Audio elements wrapper
│   │
│   └── BottomPlayerBarConnected.tsx  🔄 REFACTORED - Orchestration only
│
└── services/
    └── mseStreamingService.ts       ✅ DONE - MSE utilities
```

---

## 🔄 **Refactored BottomPlayerBarConnected.tsx**

After refactoring, the main component will be ~200 lines (down from 970):

```typescript
export const BottomPlayerBarConnected: React.FC<Props> = ({
  onToggleLyrics,
  onTimeUpdate
}) => {
  // Hooks
  const playerAPI = usePlayerAPI();
  const { settings: enhancementSettings } = useEnhancement();
  const audioPlayback = useAudioPlayback({
    currentTrack: playerAPI.currentTrack,
    enhancementSettings,
    onTimeUpdate,
  });
  const gaplessPlayback = useGaplessPlayback({
    enabled: true,
    audioRef: audioPlayback.audioRef,
  });

  return (
    <PlayerContainer>
      {/* Progress bar */}
      <ProgressBar
        currentTime={playerAPI.currentTime}
        duration={playerAPI.duration}
        onSeek={playerAPI.seek}
      />

      {/* Main player content */}
      <Box display="flex" alignItems="center">
        {/* Track info */}
        <TrackInfo
          track={playerAPI.currentTrack}
          isLoved={isLoved}
          onToggleLove={handleToggleLove}
          onToggleLyrics={onToggleLyrics}
        />

        {/* Player controls */}
        <PlayerControls
          isPlaying={playerAPI.isPlaying}
          volume={playerAPI.volume}
          onPlayPause={playerAPI.togglePlayPause}
          onNext={playerAPI.next}
          onPrevious={playerAPI.previous}
          onVolumeChange={playerAPI.setVolume}
          enhancementEnabled={enhancementSettings.enabled}
          onEnhancementToggle={setEnhancementEnabled}
        />
      </Box>

      {/* Audio elements (hidden) */}
      <AudioElements
        audioRef={audioPlayback.audioRef}
        nextAudioRef={audioPlayback.nextAudioRef}
        onTimeUpdate={handleTimeUpdate}
        onEnded={handleEnded}
      />
    </PlayerContainer>
  );
};
```

---

## 🎯 **MSE Integration After Refactoring**

With the refactored structure, MSE integration becomes simple:

### In useAudioPlayback.ts
```typescript
export function useAudioPlayback(options) {
  const mse = useMSEController();
  const audioRef = useRef<HTMLAudioElement>(null);

  // Initialize MSE
  useEffect(() => {
    if (options.useMSE && mse.isSupported) {
      const objectUrl = mse.initializeMSE();
      if (audioRef.current && objectUrl) {
        audioRef.current.src = objectUrl;
      }
    }
  }, [options.useMSE, mse.isSupported]);

  // Load track function
  const loadTrack = useCallback(async (trackId, preset, intensity) => {
    if (options.useMSE) {
      // MSE mode: Load first chunk
      await mse.loadChunk({ trackId, chunkIndex: 0, preset, intensity });
      prefetchNextChunks(0);
    } else {
      // HTML5 mode: Load full file
      const url = `/api/player/stream/${trackId}?preset=${preset}&intensity=${intensity}`;
      audioRef.current.src = url;
      audioRef.current.load();
    }
  }, [options.useMSE, mse]);

  return { audioRef, loadTrack, switchPreset, ... };
}
```

---

## 📋 **Implementation Steps**

1. ✅ **Create hooks/useAudioPlayback.ts** (Extract audio logic) - **COMPLETE**
2. ✅ **Create hooks/useGaplessPlayback.ts** (Extract gapless logic) - **COMPLETE**
3. ✅ **Create components/player/PlayerControls.tsx** (Extract controls UI) - **COMPLETE**
4. ✅ **Create components/player/TrackInfo.tsx** (Extract track info UI) - **COMPLETE**
5. ✅ **Create components/player/ProgressBar.tsx** (Extract progress bar) - **COMPLETE**
6. 🔄 **Refactor BottomPlayerBarConnected.tsx** (Use new components) - **IN PROGRESS**
7. 🔄 **Integrate MSE into useAudioPlayback** (Add MSE support) - **IN PROGRESS**
8. ⏳ **Test refactored components** (Ensure no regressions)
9. ⏳ **Enable MSE by default** (Toggle feature flag)

---

## ⏱️ **Timeline Estimate**

| Step | Task | Time | Priority |
|------|------|------|----------|
| 1 | useAudioPlayback.ts | 2-3 hours | P0 |
| 2 | useGaplessPlayback.ts | 1-2 hours | P1 |
| 3-6 | UI Components | 2-3 hours | P1 |
| 7 | Refactor main component | 1-2 hours | P0 |
| 8 | MSE integration | 1-2 hours | P0 |
| 9-10 | Testing & Polish | 2-3 hours | P0 |

**Total**: 9-15 hours

---

## ✅ **Benefits**

1. **Maintainability**: 970 lines → 200 lines main component
2. **Testability**: Each hook/component testable in isolation
3. **Reusability**: Components usable elsewhere
4. **MSE Integration**: Clean separation of MSE vs HTML5
5. **Performance**: Easier to optimize isolated pieces
6. **Developer Experience**: Easier to understand and modify

---

**Next Step**: Start with creating `useAudioPlayback.ts` hook
