/**
 * Library hooks for music library access and management
 * - Library data querying and browsing
 * - Track selection and filtering
 * - Library statistics and insights
 */

// Existing organized hooks
export { useLibraryQuery } from './useLibraryQuery';

// New hooks moved from root
export { useLibraryWithStats } from './useLibraryWithStats';
export { useLibraryStats } from './useLibraryStats';
export { useLibraryData } from './useLibraryData';
export { useTrackSelection } from './useTrackSelection';
