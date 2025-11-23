import React from 'react';
import { Box, Typography } from '@mui/material';
import { ContextMenu, ContextMenuAction } from '../shared/ContextMenu';
import { ArtistListLoadingIndicator } from './ArtistListLoadingIndicator';
import { ArtistListHeader } from './ArtistListHeader';
import { ArtistSection } from './ArtistSection';
import {
  ArtistListContainer,
  LoadMoreTrigger,
  EndOfListIndicator,
} from './CozyArtistList.styles';

interface ArtistItem {
  id: number;
  name: string;
  album_count: number;
  track_count: number;
}

interface ArtistContextMenuState {
  isOpen: boolean;
  mousePosition?: { top: number; left: number };
}

interface ArtistListContentProps {
  artists: ArtistItem[];
  totalArtists: number;
  isLoadingMore: boolean;
  hasMore: boolean;
  containerRef: React.RefObject<HTMLDivElement>;
  loadMoreTriggerRef: React.RefObject<HTMLDivElement>;
  groupedArtists: Record<string, ArtistItem[]>;
  sortedLetters: string[];
  contextMenuState: ArtistContextMenuState;
  contextActions: ContextMenuAction[];
  onArtistClick: (artistId: number, artistName: string) => void;
  onContextMenuOpen: (artist: ArtistItem, event: React.MouseEvent) => void;
  onContextMenuClose: () => void;
}

/**
 * ArtistListContent - Renders artist list with sections, pagination, and menu
 *
 * Displays:
 * - Artist header with counts
 * - Alphabetically grouped artist sections
 * - Infinite scroll trigger
 * - Loading indicator
 * - End of list message
 * - Context menu
 *
 * @example
 * <ArtistListContent
 *   artists={artists}
 *   totalArtists={100}
 *   groupedArtists={grouped}
 *   {...otherProps}
 * />
 */
export const ArtistListContent: React.FC<ArtistListContentProps> = ({
  artists,
  totalArtists,
  isLoadingMore,
  hasMore,
  containerRef,
  loadMoreTriggerRef,
  groupedArtists,
  sortedLetters,
  contextMenuState,
  contextActions,
  onArtistClick,
  onContextMenuOpen,
  onContextMenuClose,
}) => {
  return (
    <ArtistListContainer ref={containerRef}>
      <ArtistListHeader loadedCount={artists.length} totalCount={totalArtists} />

      {/* Alphabetically grouped artist sections */}
      {sortedLetters.map((letter) => (
        <ArtistSection
          key={letter}
          letter={letter}
          artists={groupedArtists[letter]}
          onArtistClick={onArtistClick}
          onContextMenu={onContextMenuOpen}
        />
      ))}

      {/* Load more trigger - invisible sentinel element */}
      {hasMore && <LoadMoreTrigger ref={loadMoreTriggerRef} />}

      {/* Loading indicator */}
      {isLoadingMore && (
        <ArtistListLoadingIndicator
          currentCount={artists.length}
          totalCount={totalArtists}
        />
      )}

      {/* End of list indicator */}
      {!hasMore && artists.length > 0 && (
        <EndOfListIndicator>
          <Typography variant="body2" color="text.secondary">
            Showing all {totalArtists} artists
          </Typography>
        </EndOfListIndicator>
      )}

      {/* Context menu */}
      <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={onContextMenuClose}
        actions={contextActions}
      />
    </ArtistListContainer>
  );
};

export default ArtistListContent;
