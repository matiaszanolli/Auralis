import React from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography
} from '@mui/material';
import AlbumArt from '../album/AlbumArt';
import {
  AlbumCard,
  AlbumTitle,
  AlbumInfo
} from './ArtistDetail.styles';

interface Album {
  id: number;
  title: string;
  year?: number;
  track_count: number;
  total_duration: number;
}

interface AlbumsTabProps {
  albums: Album[];
  onAlbumClick: (albumId: number) => void;
}

/**
 * AlbumsTab - Grid of albums for artist detail view
 *
 * Displays:
 * - Album grid with artwork
 * - Album title and metadata (year, track count)
 * - Click handler for navigation
 * - Empty state message
 */
export const AlbumsTab: React.FC<AlbumsTabProps> = ({
  albums,
  onAlbumClick
}) => {
  if (!albums || albums.length === 0) {
    return (
      <Paper
        sx={{
          padding: 4,
          textAlign: 'center',
          background: 'rgba(255,255,255,0.03)',
          borderRadius: 2,
        }}
      >
        <Typography color="text.secondary">
          No albums found for this artist
        </Typography>
      </Paper>
    );
  }

  return (
    <Box>
      <Grid container spacing={3}>
        {albums.map((album) => (
          <Grid item xs={12} sm={6} md={4} lg={3} xl={2} key={album.id}>
            <AlbumCard onClick={() => onAlbumClick(album.id)}>
              <AlbumArt
                albumId={album.id}
                size="100%"
                borderRadius={0}
              />
              <Box sx={{ p: 2 }}>
                <AlbumTitle className="album-title">
                  {album.title}
                </AlbumTitle>
                <AlbumInfo>
                  {album.year && `${album.year} • `}
                  {album.track_count} {album.track_count === 1 ? 'track' : 'tracks'}
                </AlbumInfo>
              </Box>
            </AlbumCard>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default AlbumsTab;
