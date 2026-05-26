import { MouseEvent, useCallback } from 'react';
import { Typography } from '@mui/material';
import InfiniteScroll from 'react-infinite-scroll-component';
import { ContextMenu, ContextMenuAction } from '@/components/shared/ContextMenu';
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
  onContextMenuOpen: (artist: ArtistItem, event: MouseEvent) => void;
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
export const ArtistListContent = ({
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
}: ArtistListContentProps) => {
  // #3607: stable callback identity so ArtistSection's React.memo holds.
  const handleContextMenu = useCallback(
    (e: MouseEvent, artist: ArtistItem) => onContextMenuOpen(artist, e),
    [onContextMenuOpen]
  );

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
        scrollThreshold={0.8}
        scrollableTarget="app-main-content-scroll"
      >
        <ArtistListHeader loadedCount={artists.length} totalCount={totalArtists} />

        {/* Alphabetically grouped artist sections.
            #3607: pass a stable handleContextMenu so ArtistSection's React.memo
            isn't defeated by an inline arrow. */}
        {sortedLetters.map((letter) => (
          <ArtistSection
            key={letter}
            letter={letter}
            artists={groupedArtists[letter]}
            onArtistClick={onArtistClick}
            onContextMenu={handleContextMenu}
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
