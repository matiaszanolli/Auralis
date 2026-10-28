/**
 * Library hooks for music library access and management
 * - Library data querying and browsing
 * - Track selection and filtering
 * - Library statistics and insights
 */

// Existing organized hooks
export { useLibraryQuery, useAlbumsQuery, useArtistsQuery, useTracksQuery } from './useLibraryQuery';

// New hooks moved from root
export { useLibraryWithStats } from './useLibraryWithStats';
export { useLibraryChangeSync, LIBRARY_CHANGE_MESSAGES } from './useLibraryChangeSync';
export { useLibraryPagination } from './useLibraryPagination';
export { useLibraryStats } from './useLibraryStats';
export { useLibraryScan } from './useLibraryScan';
export { useTrackSelection } from './useTrackSelection';
export { useRecentlyTouched } from './useRecentlyTouched';
export type { RecentlyTouchedEntry } from './useRecentlyTouched';
export { useScanProgress } from './useScanProgress';
export type { ScanProgress } from './useScanProgress';
export { useArtworkRevision } from './useArtworkUpdates';
