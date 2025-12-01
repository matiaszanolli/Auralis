# 🚀 Frontend Redesign - Quick Reference Card

**Print this out or bookmark it!**

---

## 📦 Phase 0 Foundation (Ready to Use)

### Types & Imports
```typescript
// WebSocket types
import type {
  WebSocketMessage,
  WebSocketMessageType,
  PlayerStateMessage,
  MasteringRecommendationMessage
} from '@/types/websocket';

// API types
import type {
  ApiResponse,
  PlayerState,
  Album,
  Artist
} from '@/types/api';

// Domain models
import type {
  Track,
  EnhancementSettings,
  AudioFingerprint,
  MasteringRecommendation
} from '@/types/domain';

import {
  ENHANCEMENT_PRESETS,
  ENHANCEMENT_PRESET_DESCRIPTIONS,
  formatDuration,
  formatDuration
} from '@/types/domain';
```

---

## 🎣 Hooks Quick Recipes

### WebSocket Subscription
```typescript
import { useWebSocketSubscription } from '@/hooks/websocket/useWebSocketSubscription';

// Subscribe to messages
useWebSocketSubscription(
  ['player_state', 'playback_started'],
  (message) => {
    console.log('Received:', message.type, message.data);
  }
);

// Get latest message
import { useWebSocketLatestMessage } from '@/hooks/websocket/useWebSocketSubscription';
const rec = useWebSocketLatestMessage('mastering_recommendation');
```

### REST API
```typescript
import { useRestAPI, useQuery, useMutation } from '@/hooks/api/useRestAPI';

// Simple GET
const api = useRestAPI();
const response = await api.get<PlayerState>('/api/player/state');

// POST
await api.post('/api/player/play', { track_path: '/music/song.wav' });

// Auto-fetch on mount
const { data, isLoading, error } = useQuery<Album[]>(
  '/api/library/albums?limit=50'
);

// Manual mutation
const { mutate, data, isLoading } = useMutation<PlayerState>(
  '/api/player/play',
  'POST'
);
await mutate({ track_path: '/path/to/track.wav' });
```

### Playback State
```typescript
import {
  usePlaybackState,
  usePlaybackPosition,
  useCurrentTrack,
  useIsPlaying,
  useVolume
} from '@/hooks/player/usePlaybackState';

// Full state
const playback = usePlaybackState();
console.log(playback.isPlaying, playback.position, playback.currentTrack);

// Individual (better performance)
const { position, duration } = usePlaybackPosition();
const track = useCurrentTrack();
const isPlaying = useIsPlaying();
const volume = useVolume();
```

### Playback Control
```typescript
import { usePlaybackControl } from '@/hooks/player/usePlaybackControl';

const {
  play,
  pause,
  seek,
  next,
  previous,
  setVolume,
  isLoading,
  error
} = usePlaybackControl();

await play();
await seek(120); // Seek to 2:00
await setVolume(0.8);
```

### Fingerprint Cache
```typescript
import {
  useFingerprintCache,
  useIsFingerprintCached,
  useCachedFingerprint,
  useFingerprintCacheStats
} from '@/hooks/fingerprint/useFingerprintCache';

// Main hook
const { state, progress, preprocess, fingerprint } = useFingerprintCache();

useEffect(() => {
  if (currentTrack) {
    preprocess(currentTrack.id);
  }
}, [currentTrack?.id]);

// Show buffering
{state === 'processing' && <ProgressBar value={progress} />}

// Check if cached
const isCached = useIsFingerprintCached(trackId);

// Get stats
const stats = useFingerprintCacheStats(); // { total, sizeMB, ... }
```

---

## 🎨 Design System
```typescript
import { tokens } from '@/design-system/tokens';

// Colors
tokens.colors.bg.primary          // Dark navy background
tokens.colors.text.primary        // White text
tokens.colors.accent.primary      // Purple accent
tokens.colors.success             // Green for success

// Spacing
tokens.spacing.xs   // 4px
tokens.spacing.sm   // 8px
tokens.spacing.md   // 16px (default)
tokens.spacing.lg   // 24px
tokens.spacing.xl   // 32px

// Typography
tokens.typography.fontSize.md     // 16px
tokens.typography.fontWeight.bold // 700
tokens.typography.fontFamily.primary

// Shadows & Radius
tokens.shadows.md               // Box shadow
tokens.borderRadius.md          // 8px

// Usage
const styles = {
  container: {
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.primary,
    borderRadius: tokens.borderRadius.md,
  },
  text: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.md,
  }
};
```

---

## 📊 WebSocket Message Types

```typescript
// Player messages
'player_state'                  // Full state sync (1Hz)
'playback_started'              // Play button clicked
'playback_paused'               // Pause button clicked
'playback_stopped'              // Stop
'track_loaded'                  // New track loaded
'track_changed'                 // Next/previous
'position_changed'              // Seek
'volume_changed'                // Volume adjust

// Enhancement messages
'enhancement_settings_changed'  // Preset/intensity changed
'mastering_recommendation'      // Recommendation for current track

// Library messages
'library_updated'               // Scan complete/files added
'metadata_updated'              // Single track metadata changed
'metadata_batch_updated'        // Multiple tracks updated
'scan_progress'                 // Scanning in progress

// Playlist messages
'playlist_created' | 'playlist_updated' | 'playlist_deleted'

// System messages
'scan_progress'                 // Library scanning
'scan_complete'                 // Scan finished
```

---

## 🔌 REST Endpoints Quick Reference

```typescript
// Player Control
POST   /api/player/play
POST   /api/player/pause
POST   /api/player/stop
PUT    /api/player/seek              { position: number }
POST   /api/player/next
POST   /api/player/previous
PUT    /api/player/volume            { volume: number }

// Queue Management
POST   /api/player/queue/add          { track_path: string }
DELETE /api/player/queue/{index}
PUT    /api/player/queue/reorder      { from_index, to_index }
POST   /api/player/queue/clear
POST   /api/player/queue/shuffle

// Library
GET    /api/library/tracks            ?limit=50&offset=0&search=query
GET    /api/library/albums            ?limit=50&offset=0
GET    /api/library/artists           ?limit=50&offset=0
GET    /api/library/albums/{id}
GET    /api/library/artists/{id}

// Metadata
PUT    /api/metadata/tracks/{id}      { title, artist, album, ... }
POST   /api/metadata/batch            { track_ids[], updates }

// Enhancement
GET    /api/enhancement/settings
PUT    /api/enhancement/settings      { enabled, preset, intensity }
GET    /api/player/mastering/recommendation/{track_id}

// Search
GET    /api/library/search            ?q=query&type=all&limit=10

// Health
GET    /api/health
GET    /api/cache/stats
```

---

## ✅ Component Checklist

Before committing any component:

- [ ] **Code Quality**
  - [ ] < 300 lines
  - [ ] No duplicate code
  - [ ] TypeScript strict mode
  - [ ] JSDoc comments

- [ ] **Styling**
  - [ ] Uses `tokens` only (no hardcoded colors)
  - [ ] Responsive (mobile + desktop)
  - [ ] Dark mode compatible
  - [ ] Accessible focus states

- [ ] **Testing**
  - [ ] Unit test file exists
  - [ ] > 80% code coverage
  - [ ] Integration tests included
  - [ ] `npm test` passes

- [ ] **Performance**
  - [ ] React.memo if expensive
  - [ ] useCallback for handlers
  - [ ] useMemo for expensive calculations
  - [ ] No unnecessary re-renders

- [ ] **Accessibility**
  - [ ] aria-labels on buttons
  - [ ] Keyboard navigation works
  - [ ] Color contrast OK
  - [ ] Screen reader friendly

---

## 🧪 Testing Patterns

```typescript
// Test imports
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { act } from '@testing-library/react';
import { vi } from 'vitest';

// Render with providers
import { render as renderWithProviders } from '@/test/test-utils';

// Mock WebSocket
import { setWebSocketManager } from '@/hooks/websocket/useWebSocketSubscription';

// Basic test
it('should render player', () => {
  const { getByRole } = render(<PlayerBar />);
  expect(getByRole('button', { name: /play/i })).toBeInTheDocument();
});

// Test with async
it('should fetch data', async () => {
  const { data } = useQuery('/api/library/tracks');
  await waitFor(() => {
    expect(data).not.toBeNull();
  });
});

// Mock API
const mockApi = vi.fn().mockResolvedValue({ id: 1 });
api.get = mockApi;

// Test WebSocket
act(() => {
  mockWebSocket.send({
    type: 'player_state',
    data: { isPlaying: true, ... }
  });
});
```

---

## 🚨 Common Mistakes to Avoid

❌ **DON'T:**
```typescript
// Hardcoded colors
backgroundColor: '#ffffff'

// Direct API calls without hooks
fetch('/api/player/play')

// Missing cleanup
useEffect(() => {
  subscription.listen(...)
  // No return cleanup!
})

// Non-memoized callbacks in props
onClick={() => play()} // Creates new function each render

// Duplicate state
const [player, setPlayer] = useState(initialState);
const [isPlaying, setIsPlaying] = useState(false); // Duplicate!

// Infinite loops
useEffect(() => {
  fetch('/api/data');
}, [fetch]) // fetch is recreated each render!
```

✅ **DO:**
```typescript
// Use design tokens
backgroundColor: tokens.colors.bg.primary

// Use hooks for API
const api = useRestAPI();
await api.post('/api/player/play');

// Cleanup on unmount
useEffect(() => {
  const unsub = subscribe(...);
  return unsub; // Clean up
}, [])

// Memoize callbacks
const handlePlay = useCallback(() => play(), [play])

// Single source of truth
const { isPlaying } = usePlaybackState()

// Stable dependencies
useEffect(() => {
  fetch('/api/data');
}, []) // No dependencies
```

---

## 📞 Who to Ask

| Question | Contact |
|----------|---------|
| "How do I use X hook?" | See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) or hook JSDoc |
| "What types should I import?" | [src/types/](../../auralis-web/frontend/src/types/) |
| "How do I style a component?" | [Design tokens](../../auralis-web/frontend/src/design-system/tokens.ts) |
| "Why is my test failing?" | Check [TESTING_GUIDELINES.md](../../docs/development/TESTING_GUIDELINES.md) |
| "What's the API for X endpoint?" | [Backend routers](../../auralis-web/backend/routers/) or [WEBSOCKET_API.md](../../auralis-web/backend/WEBSOCKET_API.md) |
| "How do I debug WebSocket?" | Check [ARCHITECTURE_V3.md § Debugging](ARCHITECTURE_V3.md) |

---

## 🔗 Important Links

**Roadmaps:**
- [FRONTEND_REDESIGN_ROADMAP_2_0.md](../roadmaps/FRONTEND_REDESIGN_ROADMAP_2_0.md) - Full specs
- [PHASE0_COMPLETE_SUMMARY.md](PHASE0_COMPLETE_SUMMARY.md) - What's done
- [PHASE1_2_3_LAUNCH_CHECKLIST.md](PHASE1_2_3_LAUNCH_CHECKLIST.md) - Launch guide

**Code:**
- [src/types/](../../auralis-web/frontend/src/types/) - Type definitions
- [src/hooks/](../../auralis-web/frontend/src/hooks/) - All hooks
- [src/design-system/tokens.ts](../../auralis-web/frontend/src/design-system/tokens.ts) - Styling

**Backend:**
- [auralis-web/backend/WEBSOCKET_API.md](../../auralis-web/backend/WEBSOCKET_API.md) - Messages
- [auralis-web/backend/routers/](../../auralis-web/backend/routers/) - Endpoints

---

## 📋 Daily Checklist

**Every Morning:**
- [ ] `git pull` latest changes
- [ ] `npm install` (if deps changed)
- [ ] `npm run typecheck` - no errors
- [ ] `npm test -- --watch` - tests pass

**Before Commit:**
- [ ] `npm run typecheck` passes
- [ ] `npm test` passes
- [ ] Code formatted (follow ESLint)
- [ ] Components < 300 lines
- [ ] Uses design tokens

**Before PR:**
- [ ] Tested locally
- [ ] No console errors
- [ ] No TypeScript errors
- [ ] Coverage > 80%
- [ ] Documented in comments

---

**Last Updated:** November 30, 2025
**Valid Through:** Phase 4 (Jan 10, 2026)
