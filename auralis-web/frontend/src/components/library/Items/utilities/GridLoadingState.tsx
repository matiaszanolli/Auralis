/**
 * GridLoadingState Component
 *
 * Displays a loading state with spinner and text message when
 * pagination is in progress (loading more items).
 *
 * Used by: CozyAlbumGrid, TrackListView (list view)
 *
 * Usage:
 * ```tsx
 * {isLoadingMore && (
 *   <GridLoadingState current={albums.length} total={totalAlbums} itemType="albums" />
 * )}
 * ```
 */

import React from 'react';
import {
  LoadingIndicatorBox,
  LoadingSpinner,
  LoadingText
} from '@/components/library/Styles/Grid.styles';

interface GridLoadingStateProps {
  current?: number;
  total?: number;
  itemType?: string; // e.g., "tracks", "albums"
  children?: React.ReactNode;
}

export const GridLoadingState = ({
  current,
  total,
  itemType = 'items',
  children
}: GridLoadingStateProps) => {
  return (
    <LoadingIndicatorBox>
      <LoadingSpinner />
      <LoadingText variant="body2">
        {children || (
          <>
            Loading more {itemType}
            {current !== undefined && total !== undefined && ` (${current}/${total})`}
            ...
          </>
        )}
      </LoadingText>
    </LoadingIndicatorBox>
  );
};

export default GridLoadingState;
