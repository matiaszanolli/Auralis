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
// Normal (unprocessed) playback is intentionally not wired to any UI: the
// play_normal wire command is what a disconnected client could send to
// cancel the live enhanced-audio session. Re-add via PlaybackSessionContext
// if it's needed again, not as an independent control plane.

// usePlayEnhanced sub-hooks (#4077 decomposition)
export { useFingerprintStatus, type FingerprintStatus } from './useFingerprintStatus';
export { useEnhancedStreamStart, type CurrentTrackInfo } from './useEnhancedStreamStart';
export { useEnhancedSeek } from './useEnhancedSeek';
export { useEnhancedPlayCommand, type PlayEnhanced } from './useEnhancedPlayCommand';

// useEnhancedPlaybackShortcuts (Phase 3.4) removed: it was never actually
// called anywhere (only its types were imported), and its Shift+A/S/W/B/P
// preset shortcuts named four presets that no longer exist (#4861 follow-up).
