# Volume Scale Inconsistency Fix

**Issue**: [#2116](https://github.com/sergree/matchering/issues/2116) - Volume scale inconsistency (0-100 in Redux vs 0-1 in engine)

**Severity**: MEDIUM

**Status**: ✅ FIXED

## Problem

Volume scale was inconsistent across the application:
- **Backend** `PlayerState` stores volume as `int` 0-100 ([player_state.py:54](../../auralis-web/backend/player_state.py#L54))
- **Frontend Redux** stores volume as 0-100 ([playerSlice.ts:73](../../auralis-web/frontend/src/store/slices/playerSlice.ts#L73))
- **AudioPlaybackEngine** expects volume as 0-1 ([AudioPlaybackEngine.ts:210](../../auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts#L210))
- **VolumeControl** component works with 0-1 ([VolumeControl.tsx:22](../../auralis-web/frontend/src/components/player/VolumeControl.tsx#L22))

### The Bug

When the user changed the volume slider:
1. `VolumeControl` called `handleVolumeChange(vol)` with 0-1 scale
2. `handleVolumeChange` called `setStreamingVolume(vol)` to update `AudioPlaybackEngine` ✓
3. **BUT: Volume was NEVER saved back to Redux!**
4. When backend broadcasted `player_state`, Redux was overwritten with old value
5. **Result: UI volume slider reverted to old volume after WebSocket update**

## Solution

### Changes

**File**: [Player.tsx](../../auralis-web/frontend/src/components/player/Player.tsx)

1. **Import `setVolume` action** (line 48):
   ```typescript
   import { setCurrentTrack, setVolume } from '@/store/slices/playerSlice';
   ```

2. **Persist volume changes to Redux** (lines 204-218):
   ```typescript
   const handleVolumeChange = async (vol: number) => {
     try {
       // Volume is 0-1 range in WebSocket/AudioEngine, 0-100 in Redux/Backend
       setStreamingVolume(vol);

       // Persist volume to Redux (convert 0-1 to 0-100)
       const volumeForRedux = Math.round(vol * 100);
       dispatch(setVolume(volumeForRedux));

       console.log('[Player] Volume changed:', vol, '(Redux:', volumeForRedux, ')');
     } catch (err) {
       console.error('[Player] Volume command error:', err);
     }
   };
   ```

3. **Fix misleading comment** (line 248):
   ```typescript
   // Extract volume from Redux state (0-100 range)
   const volume = useMemo(() => {
     return state.volume ?? 50;
   }, [state.volume, isStreaming]);
   ```

### Volume Flow (After Fix)

```
User moves slider (0-1)
    ↓
VolumeControl.onChange(vol) → 0-1
    ↓
Player.handleVolumeChange(vol)
    ├─→ setStreamingVolume(vol)    [0-1 to AudioPlaybackEngine]
    └─→ dispatch(setVolume(vol*100)) [0-100 to Redux]
         ↓
    Redux stores 0-100
         ↓
    WebSocket sync receives player_state (0-100 from backend)
         ↓
    Redux updates (already correct scale)
         ↓
    Player.tsx converts to 0-1 for VolumeControl (volume / 100)
         ↓
    VolumeControl displays correctly
```

### Scale Conversions

| Location | Scale | Type | Conversion |
|----------|-------|------|------------|
| Backend `PlayerState.volume` | 0-100 | `int` | - |
| Redux `playerSlice.volume` | 0-100 | `number` | - |
| Player.tsx `volume` variable | 0-100 | `number` | Read from Redux |
| VolumeControl component prop | 0-1 | `number` | `volume / 100` |
| VolumeControl slider value | 0-1 | `number` | Native range input |
| handleVolumeChange parameter | 0-1 | `number` | From VolumeControl |
| setStreamingVolume call | 0-1 | `number` | Passed through |
| AudioPlaybackEngine.setVolume | 0-1 | `number` | Clamps 0-1 |
| Web Audio API gainNode.gain.value | 0-1 | `number` | Native API |
| Redux dispatch setVolume | 0-100 | `number` | `vol * 100` |

## Testing

**Test File**: [VolumeScale.test.tsx](../../auralis-web/frontend/src/components/player/__tests__/VolumeScale.test.tsx)

### Test Coverage

✅ 8 tests, all passing:

1. **should store volume as 0-100 in Redux**
   - Verifies Redux stores volume in 0-100 range

2. **should convert volume to 0-1 for VolumeControl component**
   - Verifies VolumeControl slider receives 0-1 value

3. **should display volume percentage correctly**
   - Verifies UI shows correct percentage (e.g., "70%")

4. **should persist volume changes to Redux when slider changes**
   - Verifies volume changes are saved to Redux in 0-100 scale

5. **should call AudioPlaybackEngine.setVolume with 0-1 scale**
   - Verifies audio engine receives correct 0-1 scale

6. **should handle volume changes at boundary values**
   - Tests minimum (0) and maximum (100/1.0) values

7. **should round volume correctly when converting 0-1 to 0-100**
   - Verifies Math.round() works correctly (0.754 → 75, 0.756 → 76)

8. **should maintain volume consistency after WebSocket player_state update**
   - Verifies volume remains consistent when backend broadcasts state

### Test Results

```bash
$ npm run test -- VolumeScale.test.tsx

 ✓ src/components/player/__tests__/VolumeScale.test.tsx (8 tests) 406ms

 Test Files  1 passed (1)
      Tests  8 passed (8)
```

## Verification Steps

1. **Manual Testing**:
   - Launch Auralis Web: `python launch-auralis-web.py --dev`
   - Navigate to player UI
   - Change volume slider
   - Verify volume persists after:
     - Page refresh
     - WebSocket reconnection
     - Track changes
     - Playback state changes

2. **Automated Testing**:
   ```bash
   npm run test -- VolumeScale.test.tsx
   ```

3. **Type Checking**:
   ```bash
   npm run type-check
   ```

## Related Files

- [auralis-web/backend/player_state.py](../../auralis-web/backend/player_state.py) - Backend PlayerState schema
- [auralis-web/frontend/src/store/slices/playerSlice.ts](../../auralis-web/frontend/src/store/slices/playerSlice.ts) - Redux player state
- [auralis-web/frontend/src/components/player/Player.tsx](../../auralis-web/frontend/src/components/player/Player.tsx) - Main player component
- [auralis-web/frontend/src/components/player/VolumeControl.tsx](../../auralis-web/frontend/src/components/player/VolumeControl.tsx) - Volume control UI
- [auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts](../../auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts) - Audio engine
- [auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts](../../auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts) - WebSocket streaming hook
- [auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts](../../auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts) - WebSocket state sync

## Notes

- No backend changes required (volume control is purely client-side via Web Audio API)
- Backend `PlayerState.volume` is only for state synchronization
- WebSocket `player_state` message includes volume for consistency
- All volume operations are non-blocking (async)
- Volume changes are logged for debugging: `[Player] Volume changed: 0.8 (Redux: 80)`

## Migration Guide

No migration needed - this is a bug fix with backward-compatible changes.

## Future Improvements

- Consider adding volume change debouncing to reduce Redux dispatch frequency
- Add volume change animation/transition for smoother UX
- Persist volume to localStorage for cross-session persistence
- Add keyboard shortcuts for volume control (e.g., Ctrl+↑/↓)
