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
export { usePlaybackState } from './usePlaybackState';
export { useQueueHistory } from './useQueueHistory';
export { useQueueRecommendations } from './useQueueRecommendations';
export { useQueueSearch } from './useQueueSearch';
export { useQueueStatistics } from './useQueueStatistics';

// New hooks moved from root
export { usePlayerWithAudio } from './usePlayerWithAudio';
export { usePlayerControls } from './usePlayerControls';
export { usePlayerStreaming } from './usePlayerStreaming';
export { usePlayerStateSync } from './usePlayerStateSync';
export { usePlayerDisplay } from './usePlayerDisplay';
export { usePlayerEventHandlers } from './usePlayerEventHandlers';
export { usePlayerEnhancementSync } from './usePlayerEnhancementSync';
export { usePlayerTrackLoader } from './usePlayerTrackLoader';
export { usePlayerAPI } from './usePlayerAPI';
export { useUnifiedWebMAudioPlayer } from './useUnifiedWebMAudioPlayer';
