/**
 * EndOfListIndicator Component
 *
 * Displays a message when all items have been loaded and no more
 * items are available for pagination. Provides user feedback that
 * they've reached the end of the list.
 *
 * Used by: TrackListView, CozyAlbumGrid
 *
 * Usage:
 * ```tsx
 * {!hasMore && items.length > 0 && (
 *   <EndOfListIndicator>
 *     Showing all {totalCount} tracks
 *   </EndOfListIndicator>
 * )}
 * ```
 */

import React from 'react';
import {
  EndOfListIndicator as StyledContainer,
  EndOfListText as StyledText
} from '@/components/library/Styles/Grid.styles';

interface EndOfListIndicatorProps {
  children?: React.ReactNode;
  count?: number;
  itemType?: string; // e.g., "tracks", "albums"
}

export const EndOfListIndicator = ({
  children,
  count,
  itemType = 'items'
}: EndOfListIndicatorProps) => {
  return (
    <StyledContainer>
      <StyledText variant="body2">
        {children || (count !== undefined ? `Showing all ${count} ${itemType}` : 'End of list')}
      </StyledText>
    </StyledContainer>
  );
};

export default EndOfListIndicator;
