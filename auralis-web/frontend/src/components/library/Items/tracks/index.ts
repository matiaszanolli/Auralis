/**
 * Track Row Components Module
 *
 * Components for displaying individual track rows with playback controls, album art, and metadata.
 * Supports multiple interaction patterns:
 * - Standard playback (TrackRow)
 * - Multi-selection (SelectableTrackRow)
 * - Drag-and-drop (DraggableTrackRow)
 */

export { default as TrackRow } from './TrackRow';
export { default as DraggableTrackRow } from './DraggableTrackRow';
export { default as SelectableTrackRow } from './SelectableTrackRow';

// Sub-components (internal use, re-exported for flexibility)
export { default as TrackRowPlayButton } from './TrackRowPlayButton';
export { default as TrackRowAlbumArt } from './TrackRowAlbumArt';
export { default as TrackRowMetadata } from './TrackRowMetadata';
export { default as TrackPlayIndicator } from './TrackPlayIndicator';

// Custom hooks
export { useTrackFormatting } from './useTrackFormatting';
export { useTrackImage } from './useTrackImage';
export { useTrackRowHandlers } from './useTrackRowHandlers';
export { useTrackContextMenu } from './useTrackContextMenu';
export { useTrackRowSelection } from './useTrackRowSelection';
