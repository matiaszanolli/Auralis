/**
 * Enhancement Components
 *
 * UI components for WebSocket-based audio streaming and enhanced playback.
 * Includes playback controls, progress visualization, error handling, and integration panel.
 */

export { EnhancedPlaybackControls } from './EnhancedPlaybackControls';
export type { EnhancedPlaybackControlsProps } from './EnhancedPlaybackControls';

export { StreamingProgressBar } from './StreamingProgressBar';
export type { StreamingProgressBarProps } from './StreamingProgressBar';

export { StreamingErrorBoundary, StreamingErrorType, ErrorSeverity } from './StreamingErrorBoundary';
export type { StreamingErrorBoundaryProps } from './StreamingErrorBoundary';

export { PlayerEnhancementPanel } from './PlayerEnhancementPanel';
export type { PlayerEnhancementPanelProps } from './PlayerEnhancementPanel';
