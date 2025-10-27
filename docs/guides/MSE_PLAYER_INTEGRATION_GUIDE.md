# MSE Player Integration Guide

**Date**: October 27, 2025
**Topic**: Frontend integration guide for MSEPlayer progressive streaming

---

## Quick Start

### Basic Usage

```typescript
import { useMSEPlayer } from '../hooks/useMSEPlayer';

function MyPlayer() {
  const { initialize, play, pause, switchPreset, state } = useMSEPlayer({
    enhanced: true,
    preset: 'adaptive',
    debug: true
  });

  // Initialize with track
  await initialize(trackId);

  // Play
  await play();

  // Switch preset instantly!
  await switchPreset('punchy'); // <100ms with L1 cache
}
```

---

## Architecture Overview

### Component Structure

```
MSEPlayer (Core Class)
├─ MediaSource - Browser API for progressive streaming
├─ SourceBuffer - Audio chunk buffer management
├─ Chunk Loading - Progressive fetch with multi-tier buffer
└─ Event System - React-friendly event handling

useMSEPlayer (React Hook)
├─ Lifecycle Management - Auto cleanup
├─ State Management - React state integration
├─ Event Handlers - Automatic registration
└─ TypeScript Support - Full type safety

MSEPlayerExample (Reference Component)
├─ Playback Controls
├─ Preset Switching
├─ Performance Monitoring
└─ Debug Output
```

### Data Flow

```
User Action (e.g., switch preset)
    ↓
useMSEPlayer Hook
    ↓
MSEPlayer.switchPreset()
    ↓
Clear SourceBuffer
    ↓
Fetch new chunks from /api/mse/stream/{track_id}/chunk/{idx}
    ↓
Multi-Tier Buffer (L1/L2/L3 cache check)
    ↓
Append chunks to SourceBuffer
    ↓
Resume playback (same position)
    ↓
Update React state
    ↓
UI updates (instant!)
```

---

## MSEPlayer Class API

### Constructor

```typescript
const player = new MSEPlayer(audioElement, {
  apiBaseUrl: 'http://localhost:8765',
  chunkDuration: 30,
  enhanced: true,
  preset: 'adaptive',
  intensity: 1.0,
  bufferAhead: 3,
  debug: false
});
```

### Methods

**`static isSupported(): boolean`**
- Check if MSE is supported in current browser
- Returns `true` for Chrome, Firefox, Edge, Safari desktop/iPad
- Returns `false` for Safari iPhone (<iOS 17)

**`async initialize(trackId: number): Promise<void>`**
- Load track metadata from backend
- Create MediaSource and SourceBuffer
- Fetch initial chunks (first 3)
- Transitions state: `idle` → `loading` → `ready`

**`async play(): Promise<void>`**
- Start playback
- Requires `state === 'ready'` or `'paused'`
- Throws error if not initialized

**`pause(): void`**
- Pause playback
- Maintains current position

**`seek(time: number): void`**
- Seek to specific position in seconds
- Automatically loads required chunks

**`async switchPreset(preset: string): Promise<void>`**
- **THE MAGIC METHOD** - Instant preset switching!
- Clears SourceBuffer
- Reloads chunks with new preset
- Resumes at same position
- Target latency: <100ms (L1 cache hit)

**`updateSettings(settings: Partial<MSEPlayerConfig>): void`**
- Update configuration dynamically
- Changes apply to future operations

**`getState(): MSEPlayerState`**
- Get current player state
- States: `'idle' | 'loading' | 'ready' | 'playing' | 'paused' | 'buffering' | 'error'`

**`getMetadata(): StreamMetadata | null`**
- Get stream metadata
- Available after `initialize()` completes

**`on(event: MSEPlayerEvent, handler: Function): void`**
- Register event handler
- Events: `'statechange' | 'timeupdate' | 'ended' | 'error' | 'chunkloaded' | 'presetswitched'`

**`off(event: MSEPlayerEvent, handler: Function): void`**
- Unregister event handler

**`destroy(): void`**
- Cleanup and destroy player
- Called automatically by useMSEPlayer on unmount

### Events

**`statechange`**
```typescript
player.on('statechange', ({ oldState, newState }) => {
  console.log(`State: ${oldState} → ${newState}`);
});
```

**`timeupdate`**
```typescript
player.on('timeupdate', ({ currentTime }) => {
  console.log(`Time: ${currentTime}s`);
});
```

**`chunkloaded`**
```typescript
player.on('chunkloaded', (metadata: ChunkMetadata) => {
  console.log(`Chunk ${metadata.chunk_idx}: ${metadata.cache_tier} cache, ${metadata.latency_ms}ms`);
});
```

**`presetswitched`**
```typescript
player.on('presetswitched', ({ oldPreset, newPreset }) => {
  console.log(`Preset: ${oldPreset} → ${newPreset}`);
});
```

**`ended`**
```typescript
player.on('ended', () => {
  console.log('Playback finished');
});
```

**`error`**
```typescript
player.on('error', ({ error }) => {
  console.error('Player error:', error);
});
```

---

## useMSEPlayer Hook API

### Usage

```typescript
const {
  player,              // MSEPlayer instance
  state,               // Current state
  metadata,            // Stream metadata
  currentTime,         // Playback position
  isSupported,         // Browser support
  initialize,          // Initialize function
  play,                // Play function
  pause,               // Pause function
  seek,                // Seek function
  switchPreset,        // Switch preset function
  updateSettings,      // Update settings function
  getAudioElement,     // Get audio element
  lastChunk,           // Last loaded chunk metadata
  presetSwitchStats    // Performance stats
} = useMSEPlayer(config);
```

### Configuration

```typescript
interface UseMSEPlayerConfig {
  /** Audio element (optional, creates one if not provided) */
  audioElement?: HTMLAudioElement;

  /** Auto-play after initialization */
  autoPlay?: boolean;

  /** Backend API base URL */
  apiBaseUrl?: string;

  /** Chunk duration in seconds */
  chunkDuration?: number;

  /** Enable audio enhancement */
  enhanced?: boolean;

  /** Enhancement preset */
  preset?: string;

  /** Enhancement intensity (0-1) */
  intensity?: number;

  /** Number of chunks to buffer ahead */
  bufferAhead?: number;

  /** Enable debug logging */
  debug?: boolean;
}
```

### Return Values

**`player: MSEPlayer | null`**
- Direct access to MSEPlayer instance
- Null until initialized

**`state: MSEPlayerState`**
- Current player state
- Updates automatically via events

**`metadata: StreamMetadata | null`**
- Track metadata (duration, chunks, etc.)
- Available after initialization

**`currentTime: number`**
- Current playback position in seconds
- Updates continuously during playback

**`isSupported: boolean`**
- True if browser supports MSE
- Check before rendering player UI

**`lastChunk: ChunkMetadata | null`**
- Metadata for most recently loaded chunk
- Includes cache tier and latency

**`presetSwitchStats: { count: number; avgLatencyMs: number }`**
- Performance tracking for preset switches
- Updated after each switch

---

## Integration Patterns

### Pattern 1: Simple Player

```typescript
function SimplePlayer({ trackId }: { trackId: number }) {
  const { initialize, play, pause, state, currentTime, metadata } = useMSEPlayer({
    enhanced: true,
    preset: 'adaptive'
  });

  useEffect(() => {
    initialize(trackId);
  }, [trackId]);

  return (
    <div>
      <button onClick={play} disabled={state !== 'ready'}>Play</button>
      <button onClick={pause} disabled={state !== 'playing'}>Pause</button>
      <div>{currentTime.toFixed(1)} / {metadata?.duration.toFixed(1)}</div>
    </div>
  );
}
```

### Pattern 2: Preset Switcher

```typescript
function PresetSwitcher() {
  const { switchPreset, state } = useMSEPlayer();
  const [currentPreset, setCurrentPreset] = useState('adaptive');

  const handleSwitch = async (preset: string) => {
    const start = performance.now();
    await switchPreset(preset);
    const latency = performance.now() - start;
    console.log(`Switched in ${latency.toFixed(1)}ms`);
    setCurrentPreset(preset);
  };

  return (
    <select value={currentPreset} onChange={(e) => handleSwitch(e.target.value)}>
      <option value="adaptive">Adaptive</option>
      <option value="gentle">Gentle</option>
      <option value="warm">Warm</option>
      <option value="bright">Bright</option>
      <option value="punchy">Punchy</option>
    </select>
  );
}
```

### Pattern 3: Performance Monitor

```typescript
function PerformanceMonitor() {
  const { lastChunk, presetSwitchStats } = useMSEPlayer();

  return (
    <div>
      {lastChunk && (
        <div>
          Chunk #{lastChunk.chunk_idx}: {lastChunk.cache_tier} cache
          ({lastChunk.latency_ms}ms)
        </div>
      )}
      {presetSwitchStats.count > 0 && (
        <div>
          Preset switches: {presetSwitchStats.count}
          (avg: {presetSwitchStats.avgLatencyMs.toFixed(1)}ms)
        </div>
      )}
    </div>
  );
}
```

### Pattern 4: Full Integration (BottomPlayerBar)

```typescript
function BottomPlayerBar() {
  const {
    initialize,
    play,
    pause,
    switchPreset,
    state,
    currentTime,
    metadata,
    isSupported
  } = useMSEPlayer({
    enhanced: true,
    preset: 'adaptive',
    bufferAhead: 3,
    debug: process.env.NODE_ENV === 'development'
  });

  // Handle current track changes from queue
  useEffect(() => {
    if (currentTrack?.id) {
      initialize(currentTrack.id);
    }
  }, [currentTrack?.id]);

  // Handle preset changes from enhancement settings
  useEffect(() => {
    if (enhancementSettings.preset) {
      switchPreset(enhancementSettings.preset);
    }
  }, [enhancementSettings.preset]);

  // Render player UI...
}
```

---

## Error Handling

### Browser Support

```typescript
const { isSupported } = useMSEPlayer();

if (!isSupported) {
  return (
    <Alert severity="warning">
      MSE not supported. Falling back to file-based streaming.
    </Alert>
  );
}
```

### Initialization Errors

```typescript
try {
  await initialize(trackId);
} catch (error) {
  console.error('Failed to initialize player:', error);
  // Show error UI
  setError('Failed to load track');
}
```

### Playback Errors

```typescript
const { player } = useMSEPlayer();

useEffect(() => {
  if (!player) return;

  player.on('error', ({ error }) => {
    console.error('Playback error:', error);
    // Handle error (show toast, fallback, etc.)
  });
}, [player]);
```

### Preset Switch Errors

```typescript
try {
  await switchPreset('punchy');
} catch (error) {
  console.error('Failed to switch preset:', error);
  // UI remains on previous preset
}
```

---

## Performance Optimization

### Lazy Loading

```typescript
// Only load MSEPlayer when needed
const MSEPlayer = lazy(() => import('../services/MSEPlayer'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <MSEPlayerComponent />
    </Suspense>
  );
}
```

### Memoization

```typescript
const playerConfig = useMemo(() => ({
  enhanced: settings.enhanced,
  preset: settings.preset,
  intensity: settings.intensity
}), [settings]);

const msePlayer = useMSEPlayer(playerConfig);
```

### Debouncing Preset Changes

```typescript
const debouncedSwitchPreset = useMemo(
  () => debounce((preset: string) => switchPreset(preset), 300),
  [switchPreset]
);
```

---

## Testing

### Unit Testing (Jest)

```typescript
import { renderHook, act } from '@testing-library/react-hooks';
import { useMSEPlayer } from '../hooks/useMSEPlayer';

test('initializes player with track', async () => {
  const { result } = renderHook(() => useMSEPlayer());

  await act(async () => {
    await result.current.initialize(1);
  });

  expect(result.current.state).toBe('ready');
  expect(result.current.metadata).not.toBeNull();
});
```

### Integration Testing

```typescript
test('switches preset without playback interruption', async () => {
  const { result } = renderHook(() => useMSEPlayer());

  // Initialize and play
  await act(async () => {
    await result.current.initialize(1);
    await result.current.play();
  });

  const timeBefore = result.current.currentTime;

  // Switch preset
  await act(async () => {
    await result.current.switchPreset('punchy');
  });

  // Playback should continue from same position
  expect(result.current.state).toBe('playing');
  expect(result.current.currentTime).toBeCloseTo(timeBefore, 0.1);
});
```

---

## Troubleshooting

### Issue: Player not initializing

**Symptoms**: State stuck at 'loading'

**Causes**:
1. Backend not running
2. Track ID doesn't exist
3. CORS issues

**Solution**:
```typescript
// Check backend
fetch('http://localhost:8765/api/mse/stream/1/metadata')
  .then(r => r.json())
  .then(console.log);

// Enable debug mode
useMSEPlayer({ debug: true });
```

### Issue: Preset switch fails

**Symptoms**: Error thrown, playback stops

**Causes**:
1. SourceBuffer busy (race condition)
2. Network error fetching chunks
3. Invalid preset name

**Solution**:
```typescript
// Add retry logic
const switchWithRetry = async (preset: string, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      await switchPreset(preset);
      return;
    } catch (error) {
      if (i === retries - 1) throw error;
      await new Promise(r => setTimeout(r, 100 * (i + 1)));
    }
  }
};
```

### Issue: Chunks loading slowly

**Symptoms**: Frequent buffering, high latency

**Causes**:
1. Multi-tier buffer not warming up
2. Network congestion
3. Backend processing slow

**Solution**:
```typescript
// Monitor chunk performance
const { lastChunk } = useMSEPlayer();

useEffect(() => {
  if (lastChunk && lastChunk.latency_ms > 1000) {
    console.warn(`Slow chunk: ${lastChunk.latency_ms}ms`);
  }
}, [lastChunk]);

// Increase buffer ahead
useMSEPlayer({ bufferAhead: 5 });
```

---

## Best Practices

1. **Always check browser support**
   ```typescript
   if (!MSEPlayer.isSupported()) {
     // Use fallback player
   }
   ```

2. **Use debug mode in development**
   ```typescript
   useMSEPlayer({ debug: process.env.NODE_ENV === 'development' });
   ```

3. **Monitor performance**
   ```typescript
   const { lastChunk, presetSwitchStats } = useMSEPlayer();
   // Log stats to analytics
   ```

4. **Handle errors gracefully**
   ```typescript
   player.on('error', handleError);
   ```

5. **Clean up on unmount** (automatic with hook)
   ```typescript
   // useMSEPlayer handles cleanup automatically
   ```

6. **Debounce rapid preset changes**
   ```typescript
   const debouncedSwitch = debounce(switchPreset, 300);
   ```

7. **Preload next track** (future enhancement)
   ```typescript
   // Initialize next track in background
   ```

---

## Migration from HTML5 Audio

### Before (HTML5 Audio)

```typescript
const audioRef = useRef<HTMLAudioElement>(null);

// Load new audio
audioRef.current.src = `/api/player/stream/${trackId}?enhanced=true&preset=punchy`;
// ❌ Full file reload, 2-5 second pause

// Switch preset
audioRef.current.src = `/api/player/stream/${trackId}?enhanced=true&preset=bright`;
// ❌ Another full reload, more waiting
```

### After (MSE Player)

```typescript
const { initialize, switchPreset } = useMSEPlayer();

// Load audio
await initialize(trackId);
// ✅ Loads first 3 chunks (~1s), playback starts immediately

// Switch preset
await switchPreset('bright');
// ✅ Instant switch (<100ms), no interruption
```

### Migration Checklist

- [ ] Check browser support (`MSEPlayer.isSupported()`)
- [ ] Replace `<audio>` refs with `useMSEPlayer` hook
- [ ] Update playback controls to use hook methods
- [ ] Add preset switcher UI
- [ ] Implement error handling
- [ ] Test across browsers
- [ ] Add fallback for unsupported browsers
- [ ] Monitor performance in production

---

## Future Enhancements

1. **Managed Media Source (iPhone support)**
   - Detect MMS support
   - Use `ManagedMediaSource` class
   - Target: iOS 17.1+ Safari

2. **Gapless Playback Between Tracks**
   - Preload next track chunks
   - Seamless transitions

3. **Adaptive Bitrate Streaming**
   - Multiple quality levels
   - Automatic quality switching

4. **Offline Caching**
   - Cache chunks in IndexedDB
   - Offline playback support

5. **Advanced Buffer Strategy**
   - Predictive loading based on user behavior
   - Machine learning for preset prediction

---

## Resources

**Documentation**:
- [MSEPlayer.ts](../../auralis-web/frontend/src/services/MSEPlayer.ts) - Source code
- [useMSEPlayer.ts](../../auralis-web/frontend/src/hooks/useMSEPlayer.ts) - Hook source
- [MSEPlayerExample.tsx](../../auralis-web/frontend/src/components/MSEPlayerExample.tsx) - Example component
- [MSE_BROWSER_COMPATIBILITY.md](MSE_BROWSER_COMPATIBILITY.md) - Browser support

**MDN References**:
- [Media Source Extensions API](https://developer.mozilla.org/en-US/docs/Web/API/Media_Source_Extensions_API)
- [SourceBuffer](https://developer.mozilla.org/en-US/docs/Web/API/SourceBuffer)
- [MediaSource](https://developer.mozilla.org/en-US/docs/Web/API/MediaSource)

---

## Summary

**MSEPlayer provides**:
- ⚡ Instant preset switching (<100ms)
- 🎵 Progressive streaming (no full file loads)
- 📊 Performance monitoring
- 🔧 React integration via hooks
- 🌐 Cross-browser support (97%)
- 🚀 Production-ready API

**Start using it today!**
```typescript
import { useMSEPlayer } from '../hooks/useMSEPlayer';
```

---

**Last Updated**: October 27, 2025
**Status**: Production Ready
**Version**: 1.0.0
