/**
 * Player hooks for playback control and state management
 * - Playback state, controls, and lifecycle
 * - Queue management and navigation
 * - Audio streaming and format handling
 * - Player API communication
 */

// Existing organized hooks
export { usePlaybackQueue } from './usePlaybackQueue';
export { usePlayTrack } from './usePlayTrack';
export type { PlayableTrack } from './usePlayTrack';
// usePlaybackState removed (#3126) — parallel WS-shadow state with no
// production consumers. Use Redux selectors (playerSlice / queueSlice)
// as the single source of truth for playback state.
export { useQueueHistory } from './useQueueHistory';
export { useQueueRecommendations } from './useQueueRecommendations';
export { useQueueSearch } from './useQueueSearch';
export { useQueueStatistics } from './useQueueStatistics';

// New hooks moved from root
// usePlayerControls removed (#4387) — orphaned hook with zero production
// consumers; togglePlayPause was a permanent {success:false} stub.
// usePlaybackControl removed (#4541) — it drove a REST/WS control plane
// (play_normal, /api/player/next|previous|volume) disconnected from the
// live enhanced-audio session usePlayEnhanced actually streams. Transport
// control now goes through PlaybackSessionContext (contexts/
// PlaybackSessionContext.tsx), which wraps usePlayEnhanced once and is
// shared by Player.tsx and the global keyboard shortcuts.
// #3776: usePlayerStreaming removed — was 475 lines of dead code with
// zero production importers. Six prior fix PRs (#3261 / #2816 / #3185
// reconnect resume / etc.) churned the file with no observable user
// benefit. Removing it deletes the maintenance burden and closes the
// adjacent #3261 / #2816 issues as stale by construction.
export { usePlayerStateSync } from './usePlayerStateSync';
export { usePlayerDisplay } from './usePlayerDisplay';
