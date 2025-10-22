/**
 * CozyAlbumGrid Component
 *
 * Displays albums in a responsive grid layout with album artwork,
 * following the Auralis dark theme aesthetic with aurora gradients.
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Typography,
  styled,
  Skeleton,
} from '@mui/material';
import { colors } from '../../theme/auralisTheme';
import { AlbumArt } from '../album/AlbumArt';

interface Album {
  id: number;
  title: string;
  artist: string;
  track_count: number;
  total_duration: number;
  year?: number;
}

interface CozyAlbumGridProps {
  onAlbumClick?: (albumId: number) => void;
}

const GridContainer = styled(Box)({
  padding: '24px',
  width: '100%',
});

const AlbumCard = styled(Box)({
  cursor: 'pointer',
  transition: 'all 0.3s ease',
  borderRadius: '12px',
  padding: '12px',

  '&:hover': {
    transform: 'translateY(-4px)',
    backgroundColor: 'rgba(102, 126, 234, 0.05)',

    '& .album-title': {
      color: '#667eea',
    },
  },
});

const AlbumTitle = styled(Typography)({
  fontSize: '16px',
  fontWeight: 600,
  color: colors.text.primary,
  marginTop: '12px',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  transition: 'color 0.2s ease',
});

const AlbumArtist = styled(Typography)({
  fontSize: '14px',
  color: colors.text.secondary,
  marginTop: '4px',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

const AlbumInfo = styled(Typography)({
  fontSize: '12px',
  color: colors.text.disabled,
  marginTop: '4px',
});

const EmptyState = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  minHeight: '400px',
  color: colors.text.disabled,
  textAlign: 'center',
  padding: '40px',
});

const EmptyStateText = styled(Typography)({
  fontSize: '18px',
  fontWeight: 500,
  marginBottom: '8px',
  color: colors.text.secondary,
});

const EmptyStateSubtext = styled(Typography)({
  fontSize: '14px',
  color: colors.text.disabled,
});

export const CozyAlbumGrid: React.FC<CozyAlbumGridProps> = ({ onAlbumClick }) => {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAlbums();
  }, []);

  const fetchAlbums = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8765/api/library/albums');
      if (!response.ok) {
        throw new Error('Failed to fetch albums');
      }

      const data = await response.json();
      setAlbums(data.albums || []);
    } catch (err) {
      console.error('Error fetching albums:', err);
      setError(err instanceof Error ? err.message : 'Failed to load albums');
    } finally {
      setLoading(false);
    }
  };

  const handleAlbumClick = (albumId: number) => {
    if (onAlbumClick) {
      onAlbumClick(albumId);
    }
  };

  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  if (loading) {
    return (
      <GridContainer>
        <Grid container spacing={3}>
          {[...Array(12)].map((_, index) => (
            <Grid item xs={12} sm={6} md={4} lg={3} xl={2} key={index}>
              <Box>
                <Skeleton
                  variant="rectangular"
                  width="100%"
                  height={200}
                  sx={{ borderRadius: '8px', marginBottom: '12px' }}
                />
                <Skeleton variant="text" width="80%" />
                <Skeleton variant="text" width="60%" />
              </Box>
            </Grid>
          ))}
        </Grid>
      </GridContainer>
    );
  }

  if (error) {
    return (
      <EmptyState>
        <EmptyStateText>Error Loading Albums</EmptyStateText>
        <EmptyStateSubtext>{error}</EmptyStateSubtext>
      </EmptyState>
    );
  }

  if (albums.length === 0) {
    return (
      <EmptyState>
        <EmptyStateText>No Albums Yet</EmptyStateText>
        <EmptyStateSubtext>
          Your album library will appear here once you scan your music folder
        </EmptyStateSubtext>
      </EmptyState>
    );
  }

  return (
    <GridContainer>
      <Grid container spacing={3}>
        {albums.map((album) => (
          <Grid item xs={12} sm={6} md={4} lg={3} xl={2} key={album.id}>
            <AlbumCard onClick={() => handleAlbumClick(album.id)}>
              <AlbumArt
                albumId={album.id}
                size="100%"
                borderRadius={8}
                onClick={() => handleAlbumClick(album.id)}
              />
              <AlbumTitle className="album-title">
                {album.title}
              </AlbumTitle>
              <AlbumArtist>
                {album.artist}
              </AlbumArtist>
              <AlbumInfo>
                {album.track_count} tracks • {formatDuration(album.total_duration)}
                {album.year && ` • ${album.year}`}
              </AlbumInfo>
            </AlbumCard>
          </Grid>
        ))}
      </Grid>
    </GridContainer>
  );
};

export default CozyAlbumGrid;
