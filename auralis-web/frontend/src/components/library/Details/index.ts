/**
 * Library Details Module
 *
 * Detail view components:
 * - AlbumDetailView - Album detail view (refactored)
 * - ArtistDetailView - Artist detail view
 * - DetailViewHeader - Detail view header
 * - DetailLoading - Detail view loading state
 * - ArtistHeader - Artist header component
 *
 * AlbumDetailView subcomponents:
 * - AlbumHeaderActions - Album header with artwork and controls
 * - useAlbumDetails - Album data fetching and state management
 */

export { default as AlbumDetailView } from './AlbumDetailView';
export { default as ArtistDetailView } from './ArtistDetailView';
export { default as DetailViewHeader } from './DetailViewHeader';
export { default as DetailLoading } from './DetailLoading';
export { default as ArtistHeader } from './ArtistHeader';

// AlbumDetailView subcomponents
export { default as AlbumHeaderActions } from './AlbumHeaderActions';
export { useAlbumDetails } from './useAlbumDetails';
export type { Album, Track } from './useAlbumDetails';
