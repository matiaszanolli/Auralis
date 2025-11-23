/**
 * ContextMenu Module
 *
 * Unified context menu system for tracks, albums, artists, playlists
 * Includes main component, hook, and action generators
 */

export { default as ContextMenu } from './ContextMenu';
export type { ContextMenuProps } from './ContextMenu';

export { useContextMenu } from './useContextMenu';

export {
  getTrackContextActions,
  getAlbumContextActions,
  getArtistContextActions,
  getPlaylistContextActions,
} from './contextMenuActions';
export type { ContextMenuAction } from './contextMenuActions';

export { PlaylistSection } from './PlaylistSection';
export type { PlaylistSectionProps } from './PlaylistSection';
