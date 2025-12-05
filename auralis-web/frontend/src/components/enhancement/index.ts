/**
 * Enhancement Components
 *
 * UI components for WebSocket-based audio streaming and enhanced playback.
 * Includes playback controls, progress visualization, and error handling.
 */

export { EnhancedPlaybackControls } from './EnhancedPlaybackControls';
export type { EnhancedPlaybackControlsProps } from './EnhancedPlaybackControls';

export { StreamingProgressBar } from './StreamingProgressBar';
export type { StreamingProgressBarProps } from './StreamingProgressBar';

export { StreamingErrorBoundary, StreamingErrorType, ErrorSeverity } from './StreamingErrorBoundary';
export type { StreamingErrorBoundaryProps } from './StreamingErrorBoundary';
