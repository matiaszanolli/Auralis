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
