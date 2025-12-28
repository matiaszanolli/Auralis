/**
 * Library hooks for music library access and management
 * - Library data querying and browsing
 * - Track selection and filtering
 * - Library statistics and insights
 */

// Existing organized hooks
export { useLibraryQuery, useArtistsQuery, useTracksQuery, useAlbumsQuery as useAlbumsQueryLegacy } from './useLibraryQuery';
export { useAlbumsQuery } from './useAlbumsQuery';

// New hooks moved from root
export { useLibraryWithStats } from './useLibraryWithStats';
export { useLibraryStats } from './useLibraryStats';
export { useLibraryData } from './useLibraryData';
export { useTrackSelection } from './useTrackSelection';
export { useRecentlyTouched } from './useRecentlyTouched';
export type { RecentlyTouchedEntry } from './useRecentlyTouched';
