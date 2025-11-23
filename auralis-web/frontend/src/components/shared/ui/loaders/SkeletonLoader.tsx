/**
 * SkeletonLoader - Barrel export for all skeleton components
 *
 * Provides various skeleton (loading placeholder) components:
 * - AlbumCardSkeleton - Album grid card placeholder
 * - TrackRowSkeleton - Track list row placeholder
 * - SidebarItemSkeleton - Sidebar navigation item placeholder
 * - PlayerBarSkeleton - Player bar component placeholder
 * - LibraryGridSkeleton - Multiple album cards in grid
 * - TrackListSkeleton - Multiple track rows in list
 * - Skeleton - Generic skeleton with configurable variant
 *
 * All components use the SkeletonBox styled component for
 * consistent shimmer animation and styling.
 */

// Specific skeleton components
export { AlbumCardSkeleton } from './AlbumCardSkeleton';
export { TrackRowSkeleton } from './TrackRowSkeleton';
export { SidebarItemSkeleton } from './SidebarItemSkeleton';
export { PlayerBarSkeleton } from './PlayerBarSkeleton';

// Container skeleton components
export { LibraryGridSkeleton } from './LibraryGridSkeleton';
export { TrackListSkeleton } from './TrackListSkeleton';

// Generic skeleton component
export { Skeleton } from './Skeleton';

// Default export
export { Skeleton as default } from './Skeleton';
