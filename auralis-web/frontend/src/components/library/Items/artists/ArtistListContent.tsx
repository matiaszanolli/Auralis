import React from 'react';
import { Typography } from '@mui/material';
import InfiniteScroll from 'react-infinite-scroll-component';
import { ContextMenu, ContextMenuAction } from '../../../shared/ContextMenu';
import { ArtistListLoadingIndicator } from './ArtistListLoadingIndicator';
import { ArtistListHeader } from './ArtistListHeader';
import { ArtistSection } from './ArtistSection';
import {
  ArtistListContainer,
  EndOfListIndicator,
} from './CozyArtistList.styles';
import type { Artist } from '@/types/domain';

/**
 * Use domain Artist type (camelCase: albumCount, trackCount)
 * instead of local snake_case interface
 */
type ArtistItem = Artist;

interface ArtistContextMenuState {
  isOpen: boolean;
  mousePosition?: { top: number; left: number };
}

interface ArtistListContentProps {
  artists: ArtistItem[];
  totalArtists: number;
  isLoadingMore: boolean;
  hasMore: boolean;
  fetchMore: () => Promise<void>;
  groupedArtists: Record<string, ArtistItem[]>;
  sortedLetters: string[];
  contextMenuState: ArtistContextMenuState;
  contextActions: ContextMenuAction[];
  onArtistClick: (artist: ArtistItem) => void;
  onContextMenuOpen: (artist: ArtistItem, event: React.MouseEvent) => void;
  onContextMenuClose: () => void;
}

/**
 * ArtistListContent - Renders artist list with infinite scroll and sections
 *
 * Displays:
 * - Artist header with counts
 * - Alphabetically grouped artist sections
 * - Infinite scroll via react-infinite-scroll-component
 * - Loading indicator
 * - End of list message
 * - Context menu
 *
 * @example
 * <ArtistListContent
 *   artists={artists}
 *   totalArtists={100}
 *   hasMore={hasMore}
 *   fetchMore={fetchMore}
 *   groupedArtists={grouped}
 *   {...otherProps}
 * />
 */
export const ArtistListContent: React.FC<ArtistListContentProps> = ({
  artists,
  totalArtists,
  isLoadingMore,
  hasMore,
  fetchMore,
  groupedArtists,
  sortedLetters,
  contextMenuState,
  contextActions,
  onArtistClick,
  onContextMenuOpen,
  onContextMenuClose,
}) => {
  return (
    <ArtistListContainer>
      <InfiniteScroll
        dataLength={artists.length}
        next={fetchMore}
        hasMore={hasMore}
        loader={
          isLoadingMore && (
            <ArtistListLoadingIndicator
              currentCount={artists.length}
              totalCount={totalArtists}
            />
          )
        }
        endMessage={
          artists.length > 0 && (
            <EndOfListIndicator>
              <Typography variant="body2" color="text.secondary">
                Showing all {totalArtists} artists
              </Typography>
            </EndOfListIndicator>
          )
        }
        scrollThreshold={0.9}
      >
        <ArtistListHeader loadedCount={artists.length} totalCount={totalArtists} />

        {/* Alphabetically grouped artist sections */}
        {sortedLetters.map((letter) => (
          <ArtistSection
            key={letter}
            letter={letter}
            artists={groupedArtists[letter]}
            onArtistClick={onArtistClick}
            onContextMenu={(e, artist) => onContextMenuOpen(artist, e)}
          />
        ))}
      </InfiniteScroll>

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
