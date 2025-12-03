/**
 * AlbumGridContent Component
 *
 * Renders the grid of album cards
 */

import React from 'react';
import { Grid } from '@mui/material';
import { AlbumCard } from '../../album/AlbumCard/AlbumCard';
import { GridContainer } from '../../Styles/Grid.styles';
import InfiniteScrollTrigger from '../utilities/InfiniteScrollTrigger';
import EndOfListIndicator from '../utilities/EndOfListIndicator';
import GridLoadingState from '../utilities/GridLoadingState';

interface Album {
  id: number;
  title: string;
  artist: string;
  track_count: number;
  total_duration: number;
  year?: number;
  artwork_path?: string;
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

export const AlbumGridContent: React.FC<AlbumGridContentProps> = ({
  albums,
  hasMore,
  isLoadingMore,
  totalAlbums,
  containerRef,
  loadMoreTriggerRef,
  onAlbumClick,
}) => {
  return (
    <GridContainer ref={containerRef}>
      <Grid container spacing={3}>
        {albums.map((album) => (
          <Grid item xs={12} sm={6} md={4} lg={3} key={album.id}>
            <AlbumCard
              albumId={album.id}
              title={album.title}
              artist={album.artist}
              trackCount={album.track_count}
              duration={album.total_duration}
              year={album.year}
              hasArtwork={!!album.artwork_path}
              onClick={() => onAlbumClick(album.id)}
            />
          </Grid>
        ))}
      </Grid>

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
