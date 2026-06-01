/**
 * Player hooks for playback control and state management
 * - Playback state, controls, and lifecycle
 * - Queue management and navigation
 * - Audio streaming and format handling
 * - Player API communication
 */

// Existing organized hooks
export { usePlaybackControl } from './usePlaybackControl';
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
export { usePlayerControls } from './usePlayerControls';
// #3776: usePlayerStreaming removed — was 475 lines of dead code with
// zero production importers. Six prior fix PRs (#3261 / #2816 / #3185
// reconnect resume / etc.) churned the file with no observable user
// benefit. Removing it deletes the maintenance burden and closes the
// adjacent #3261 / #2816 issues as stale by construction.
export { usePlayerStateSync } from './usePlayerStateSync';
export { usePlayerDisplay } from './usePlayerDisplay';
export { usePlayerAPI } from './usePlayerAPI';
