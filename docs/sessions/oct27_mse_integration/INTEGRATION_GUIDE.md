# UnifiedPlayerManager Integration Guide

**Purpose**: Step-by-step guide for integrating UnifiedPlayerManager into BottomPlayerBarConnected.

**Date**: October 27, 2025

---

## Overview

The integration replaces the existing player logic with `useUnifiedPlayer` hook, which provides:
- Unified MSE + HTML5 player orchestration
- Seamless mode switching
- Position preservation
- Simplified API

---

## Integration Steps

### 1. Import useUnifiedPlayer

```typescript
import { useUnifiedPlayer } from '../hooks/useUnifiedPlayer';
```

### 2. Replace usePlayerAPI with useUnifiedPlayer

**Before**:
```typescript
const {
  currentTrack,
  isPlaying,
  currentTime,
  duration,
  volume,
  play,
  pause,
  seek,
  // ...
} = usePlayerAPI();
```

**After**:
```typescript
const player = useUnifiedPlayer({
  apiBaseUrl: 'http://localhost:8765',
  enhanced: enhancementSettings.enabled,
  preset: enhancementSettings.preset,
  intensity: enhancementSettings.intensity,
  debug: true
});

// Map to existing interface
const {
  isPlaying: playerIsPlaying,
  currentTime,
  duration,
  state: playerState,
  mode: playerMode
} = player;
```

### 3. Connect Enhancement Toggle

```typescript
const handleEnhancementToggle = async (enabled: boolean) => {
  await player.setEnhanced(enabled, enhancementSettings.preset);
  updateEnhancementSettings({ enabled });
};
```

### 4. Connect Preset Selector

```typescript
const handlePresetChange = async (preset: string) => {
  await player.setPreset(preset);
  updateEnhancementSettings({ preset });
};
```

### 5. Connect Playback Controls

```typescript
const handlePlay = async () => {
  if (!currentTrack) return;

  // Load track if not loaded
  if (playerState === 'idle') {
    await player.loadTrack(currentTrack.id);
  }

  await player.play();
};

const handlePause = () => {
  player.pause();
};

const handleSeek = async (time: number) => {
  await player.seek(time);
};
```

### 6. Track Loading

```typescript
useEffect(() => {
  if (currentTrack && currentTrack.id !== previousTrackId) {
    player.loadTrack(currentTrack.id).then(() => {
      if (autoPlay) {
        player.play();
      }
    });
  }
}, [currentTrack]);
```

### 7. Volume Control

```typescript
const handleVolumeChange = (newVolume: number) => {
  player.setVolume(newVolume / 100); // Convert 0-100 to 0-1
  setLocalVolume(newVolume);
};
```

### 8. Loading States

```typescript
// Show loading indicator during mode transitions
{player.state === 'switching' && (
  <CircularProgress size={16} />
)}

// Disable controls while switching
<PlayButton
  disabled={player.isLoading || playerState === 'switching'}
  onClick={playerIsPlaying ? handlePause : handlePlay}
>
  {playerIsPlaying ? <Pause /> : <PlayArrow />}
</PlayButton>
```

---

## State Mapping

| UnifiedPlayer State | UI Behavior |
|---------------------|-------------|
| `idle` | Ready to load track |
| `loading` | Show loading spinner |
| `ready` | Track loaded, ready to play |
| `playing` | Play button → Pause icon |
| `paused` | Pause button → Play icon |
| `buffering` | Show buffering indicator |
| `switching` | Show mode transition indicator |
| `error` | Show error message |

---

## Mode Indicators

```typescript
// Show current mode in UI
<Tooltip title={`Mode: ${playerMode === 'mse' ? 'Progressive Streaming' : 'Enhanced Processing'}`}>
  <Chip
    label={playerMode.toUpperCase()}
    size="small"
    color={playerMode === 'html5' ? 'primary' : 'default'}
  />
</Tooltip>
```

---

## Error Handling

```typescript
useEffect(() => {
  if (player.error) {
    showToast('error', `Playback error: ${player.error.message}`);
  }
}, [player.error]);
```

---

## Complete Example

```typescript
export const BottomPlayerBarConnected: React.FC = () => {
  const { enhancementSettings, updateEnhancementSettings } = useEnhancement();
  const { currentTrack } = usePlayerAPI(); // Keep for queue management

  const player = useUnifiedPlayer({
    apiBaseUrl: 'http://localhost:8765',
    enhanced: enhancementSettings.enabled,
    preset: enhancementSettings.preset,
    debug: true
  });

  // Load track when it changes
  useEffect(() => {
    if (currentTrack) {
      player.loadTrack(currentTrack.id).then(() => player.play());
    }
  }, [currentTrack?.id]);

  // Handle enhancement toggle
  const handleEnhancementToggle = async (enabled: boolean) => {
    await player.setEnhanced(enabled, enhancementSettings.preset);
    updateEnhancementSettings({ enabled });
  };

  // Handle preset change
  const handlePresetChange = async (preset: string) => {
    await player.setPreset(preset);
    updateEnhancementSettings({ preset });
  };

  return (
    <PlayerContainer>
      {/* Mode indicator */}
      <Chip label={player.mode} size="small" />

      {/* Play/Pause */}
      <PlayButton
        onClick={player.isPlaying ? player.pause : player.play}
        disabled={player.isLoading}
      >
        {player.isPlaying ? <Pause /> : <PlayArrow />}
      </PlayButton>

      {/* Progress bar */}
      <Slider
        value={player.currentTime}
        max={player.duration}
        onChange={(_, value) => player.seek(value as number)}
      />

      {/* Enhancement toggle */}
      <Switch
        checked={player.mode === 'html5'}
        onChange={(e) => handleEnhancementToggle(e.target.checked)}
        disabled={player.isLoading}
      />

      {/* Preset selector */}
      <Select
        value={enhancementSettings.preset}
        onChange={(e) => handlePresetChange(e.target.value)}
        disabled={player.mode !== 'html5' || player.isLoading}
      >
        <MenuItem value="adaptive">Adaptive</MenuItem>
        <MenuItem value="warm">Warm</MenuItem>
        <MenuItem value="bright">Bright</MenuItem>
      </Select>
    </PlayerContainer>
  );
};
```

---

## Testing Checklist

- [ ] Track loads and plays
- [ ] Play/pause works
- [ ] Seek works
- [ ] Volume control works
- [ ] Enhancement toggle works (MSE ↔ HTML5)
- [ ] Preset switching works (in enhanced mode)
- [ ] Position preserved during mode switch
- [ ] Loading states display correctly
- [ ] No dual playback conflicts
- [ ] Queue management still works
- [ ] Next/previous track works

---

## Migration Notes

**Keep from usePlayerAPI**:
- Queue management (queue, queueIndex, addToQueue, etc.)
- Track metadata (currentTrack, albums, artists)
- Favorites API (toggleFavorite)

**Replace with UnifiedPlayer**:
- Playback state (isPlaying, currentTime, duration)
- Playback controls (play, pause, seek)
- Volume control (setVolume)
- Enhancement mode switching

**Remove**:
- Old MSE integration code
- Dual player conflict workarounds
- Manual audio element management
