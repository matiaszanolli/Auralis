/**
 * Library hooks for music library access and management
 * - Library data querying and browsing
 * - Track selection and filtering
 * - Library statistics and insights
 */

// Existing organized hooks
export { useLibraryQuery, useArtistsQuery, useTracksQuery } from './useLibraryQuery';
export { useAlbumsQuery } from './useAlbumsQuery';

// New hooks moved from root
// #3645: useLibraryWithStats subsumes useLibraryData + useLibraryStats —
// the deprecated hooks were removed (no remaining consumers).
export { useLibraryWithStats } from './useLibraryWithStats';
export { useTrackSelection } from './useTrackSelection';
export { useRecentlyTouched } from './useRecentlyTouched';
export type { RecentlyTouchedEntry } from './useRecentlyTouched';
export { useScanProgress } from './useScanProgress';
export type { ScanProgress } from './useScanProgress';
export { useArtworkRevision } from './useArtworkUpdates';
