/**
 * AlbumGridContent Component
 *
 * Renders the grid of album cards
 */

import { RefObject } from 'react';
import Grid2 from '@mui/material/Unstable_Grid2';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import { GridContainer } from '@/components/library/Styles/Grid.styles';
import InfiniteScrollTrigger from '@/components/library/Items/utilities/InfiniteScrollTrigger';
import EndOfListIndicator from '@/components/library/Items/utilities/EndOfListIndicator';
import GridLoadingState from '@/components/library/Items/utilities/GridLoadingState';

interface Album {
  id: number;
  title: string;
  artist: string;
  track_count: number;
  total_duration: number;
  year?: number;
  artwork_url?: string;
}

interface AlbumGridContentProps {
  albums: Album[];
  hasMore: boolean;
  isLoadingMore: boolean;
  totalAlbums: number;
  containerRef: RefObject<HTMLDivElement>;
  loadMoreTriggerRef: RefObject<HTMLDivElement>;
  onAlbumClick: (albumId: number) => void;
}

export const AlbumGridContent = ({
  albums,
  hasMore,
  isLoadingMore,
  totalAlbums,
  containerRef,
  loadMoreTriggerRef,
  onAlbumClick,
}: AlbumGridContentProps) => {
  return (
    <GridContainer ref={containerRef}>
      <Grid2 container spacing={3}>
        {albums.map((album) => (
          <Grid2 xs={12} sm={6} md={4} lg={3} key={album.id}>
            {/* #3603: pass the parent's onAlbumClick directly (it accepts an
                albumId). AlbumCard binds the click handler internally so we
                avoid creating a new inline arrow per render — preserves
                AlbumCard's React.memo across re-renders of the parent. */}
            <AlbumCard
              albumId={album.id}
              title={album.title}
              artist={album.artist}
              trackCount={album.track_count}
              duration={album.total_duration}
              year={album.year}
              hasArtwork={!!album.artwork_url}
              onClick={onAlbumClick}
            />
          </Grid2>
        ))}
      </Grid2>

      {hasMore && <InfiniteScrollTrigger ref={loadMoreTriggerRef} />}

      {isLoadingMore && (
        <GridLoadingState current={albums.length} total={totalAlbums} itemType="albums" />
      )}

      {!hasMore && albums.length > 0 && (
        <EndOfListIndicator count={totalAlbums} itemType="albums" />
      )}
    </GridContainer>
  );
};
