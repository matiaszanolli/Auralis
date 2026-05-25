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
// usePlaybackState removed (#3126) — parallel WS-shadow state with no
// production consumers. Use Redux selectors (playerSlice / queueSlice)
// as the single source of truth for playback state.
export { useQueueHistory } from './useQueueHistory';
export { useQueueRecommendations } from './useQueueRecommendations';
export { useQueueSearch } from './useQueueSearch';
export { useQueueStatistics } from './useQueueStatistics';

// New hooks moved from root
export { usePlayerControls } from './usePlayerControls';
export { usePlayerStreaming } from './usePlayerStreaming';
export { usePlayerStateSync } from './usePlayerStateSync';
export { usePlayerDisplay } from './usePlayerDisplay';
export { usePlayerAPI } from './usePlayerAPI';
