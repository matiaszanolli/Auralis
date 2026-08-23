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
// Use Redux selectors (playerSlice / queueSlice) as the single source of
// truth for playback state.
export { useQueueHistory } from './useQueueHistory';
export { useQueueRecommendations } from './useQueueRecommendations';
export { useQueueSearch } from './useQueueSearch';
export { useQueueStatistics } from './useQueueStatistics';

// New hooks moved from root
// Transport control goes through PlaybackSessionContext (contexts/
// PlaybackSessionContext.tsx), which wraps usePlayEnhanced once and is
// shared by Player.tsx and the global keyboard shortcuts.
export { usePlayerStateSync } from './usePlayerStateSync';
export { usePlayerDisplay } from './usePlayerDisplay';
