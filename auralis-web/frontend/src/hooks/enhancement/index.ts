/**
 * Enhancement hooks for audio mastering and DSP control
 * - Audio enhancement parameter control
 * - Mastering recommendations and profiles
 * - Real-time PCM streaming via WebSocket (Phase 2.3)
 */

// Existing organized hooks
export { useEnhancementControl } from './useEnhancementControl';

// New hooks moved from root
export { useMasteringRecommendation } from './useMasteringRecommendation';

// WebSocket streaming hooks (Phase 2.3)
export { usePlayEnhanced } from './usePlayEnhanced';
export type { UsePlayEnhancedReturn } from './usePlayEnhanced';
export { usePlayNormal } from './usePlayNormal'; // fixes #2277 — was missing from barrel exports

// usePlayEnhanced sub-hooks (#4077 decomposition)
export { useFingerprintStatus, type FingerprintStatus } from './useFingerprintStatus';
export { useEnhancedStreamStart, type CurrentTrackInfo } from './useEnhancedStreamStart';
export { useEnhancedSeek } from './useEnhancedSeek';
export { useEnhancedPlayCommand, type PlayEnhanced } from './useEnhancedPlayCommand';

// Keyboard shortcuts (Phase 3.4)
export { useEnhancedPlaybackShortcuts } from './useEnhancedPlaybackShortcuts';
export type { EnhancedPlaybackShortcutsConfig, UseEnhancedPlaybackShortcutsReturn } from './useEnhancedPlaybackShortcuts';
