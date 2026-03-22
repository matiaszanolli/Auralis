/**
 * AlbumGridContent Component
 *
 * Renders the grid of album cards
 */

import React from 'react';
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
  containerRef: React.RefObject<HTMLDivElement>;
  loadMoreTriggerRef: React.RefObject<HTMLDivElement>;
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
            <AlbumCard
              albumId={album.id}
              title={album.title}
              artist={album.artist}
              trackCount={album.track_count}
              duration={album.total_duration}
              year={album.year}
              hasArtwork={!!album.artwork_url}
              onClick={() => onAlbumClick(album.id)}
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
