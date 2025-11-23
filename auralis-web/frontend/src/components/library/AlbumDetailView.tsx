import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  IconButton,
  Button,
  Skeleton,
  Tooltip
} from '@mui/material';
import { EmptyStateBox } from './EmptyStateBox';
import DetailViewHeader from './DetailViewHeader';
import { PlayButton } from './Button.styles';
import AlbumTrackTable from './AlbumTrackTable';
import { auroraOpacity } from './Color.styles';
import { tokens } from '@/design-system/tokens';
import {
  ArrowBack,
  PlayArrow,
  Pause,
  AddToQueue,
  MoreVert,
  Favorite,
  FavoriteBorder
} from '@mui/icons-material';
import AlbumArt from '../album/AlbumArt';

interface Track {
  id: number;
  title: string;
  artist: string;
  duration: number;
  track_number?: number;
  disc_number?: number;
}

interface Album {
  id: number;
  title: string;
  artist: string;
  artist_name?: string;
  year?: number;
  genre?: string;
  track_count: number;
  total_duration: number;
  tracks?: Track[];
}

interface AlbumDetailViewProps {
  albumId: number;
  onBack?: () => void;
  onTrackPlay?: (track: Track) => void;
  currentTrackId?: number;
  isPlaying?: boolean;
}

// Styled Components are imported from shared style files

export const AlbumDetailView: React.FC<AlbumDetailViewProps> = ({
  albumId,
  onBack,
  onTrackPlay,
  currentTrackId,
  isPlaying = false
}) => {
  const [album, setAlbum] = useState<Album | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFavorite, setIsFavorite] = useState(false);
  const [savingFavorite, setSavingFavorite] = useState(false);

  useEffect(() => {
    fetchAlbumDetails();
  }, [albumId]);

  const fetchAlbumDetails = async () => {
    setLoading(true);
    setError(null);

    try {
      // Use new REST API endpoint for album tracks
      const response = await fetch(`/api/albums/${albumId}/tracks`);
      if (!response.ok) {
        throw new Error('Failed to fetch album details');
      }

      const data = await response.json();

      // Transform API response to match Album interface
      const albumData: Album = {
        id: data.album_id,
        title: data.album_title,
        artist: data.artist,
        artist_name: data.artist,
        year: data.year,
        track_count: data.total_tracks,
        total_duration: data.tracks?.reduce((sum: number, t: Track) => sum + (t.duration || 0), 0) || 0,
        tracks: data.tracks || []
      };

      setAlbum(albumData);
    } catch (err) {
      console.error('Error fetching album details:', err);
      setError(err instanceof Error ? err.message : 'Failed to load album details');
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds: number): string => {
    const totalSeconds = Math.floor(seconds); // Round to integer first
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatTotalDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours} hr ${mins} min`;
    }
    return `${mins} min`;
  };

  const handlePlayAlbum = () => {
    if (album?.tracks && album.tracks.length > 0 && onTrackPlay) {
      onTrackPlay(album.tracks[0]);
    }
  };

  const handleTrackClick = (track: Track) => {
    if (onTrackPlay) {
      onTrackPlay(track);
    }
  };

  const toggleFavorite = async () => {
    setSavingFavorite(true);
    try {
      // Use first track's ID to toggle favorite (albums don't have direct favorite endpoints)
      const trackId = album?.tracks?.[0]?.id;
      if (!trackId) {
        setError('Cannot favorite album: no tracks available');
        return;
      }

      const response = await fetch(`/api/library/tracks/${trackId}/favorite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to update favorite status');
      }

      setIsFavorite(!isFavorite);
    } catch (err) {
      console.error('Error toggling favorite:', err);
      setError(err instanceof Error ? err.message : 'Failed to update favorite status');
    } finally {
      setSavingFavorite(false);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Skeleton variant="rectangular" height={400} sx={{ borderRadius: 2, mb: 4 }} />
        <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 2 }} />
      </Container>
    );
  }

  if (error || !album) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <EmptyStateBox
          title={error ? 'Error Loading Album' : 'Album not found'}
          subtitle={error || undefined}
        />
        {onBack && (
          <Box sx={{ textAlign: 'center', mt: 2 }}>
            <Button onClick={onBack} startIcon={<ArrowBack />}>
              Back to Albums
            </Button>
          </Box>
        )}
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Back Button */}
      {onBack && (
        <IconButton
          onClick={onBack}
          sx={{
            mb: 2,
            '&:hover': {
              backgroundColor: auroraOpacity.ultraLight
            }
          }}
        >
          <ArrowBack />
        </IconButton>
      )}

      {/* Album Header */}
      <DetailViewHeader
        artwork={
          <Box sx={{ width: 280, height: 280, borderRadius: 1.5, overflow: 'hidden', boxShadow: '0 8px 32px rgba(0,0,0,0.19)' }}>
            <AlbumArt
              albumId={album.id}
              size={280}
              borderRadius={0}
            />
          </Box>
        }
        title={album.title}
        subtitle={album.artist_name || album.artist}
        metadata={
          <Box>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              {album.year && `${album.year} • `}
              {album.track_count} {album.track_count === 1 ? 'track' : 'tracks'}
              {' • '}
              {formatTotalDuration(album.total_duration)}
            </Typography>
            {album.genre && (
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Genre: {album.genre}
              </Typography>
            )}
          </Box>
        }
        actions={
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <PlayButton
              startIcon={isPlaying && currentTrackId === album.tracks?.[0]?.id ? <Pause /> : <PlayArrow />}
              onClick={handlePlayAlbum}
            >
              {isPlaying && currentTrackId === album.tracks?.[0]?.id ? 'Pause' : 'Play Album'}
            </PlayButton>

            <Tooltip title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}>
              <IconButton
                onClick={toggleFavorite}
                disabled={savingFavorite}
                sx={{
                  color: isFavorite ? tokens.colors.accent.error : 'text.secondary',
                  '&:hover': {
                    backgroundColor: auroraOpacity.ultraLight
                  },
                  '&:disabled': {
                    opacity: 0.6,
                    cursor: 'not-allowed'
                  }
                }}
              >
                {isFavorite ? <Favorite /> : <FavoriteBorder />}
              </IconButton>
            </Tooltip>

            <Tooltip title="Add to queue">
              <IconButton
                sx={{
                  '&:hover': {
                    backgroundColor: auroraOpacity.ultraLight
                  }
                }}
              >
                <AddToQueue />
              </IconButton>
            </Tooltip>

            <Tooltip title="More options">
              <IconButton
                sx={{
                  '&:hover': {
                    backgroundColor: auroraOpacity.ultraLight
                  }
                }}
              >
                <MoreVert />
              </IconButton>
            </Tooltip>
          </Box>
        }
      />

      {/* Track Listing */}
      <AlbumTrackTable
        tracks={album.tracks || []}
        currentTrackId={currentTrackId}
        isPlaying={isPlaying}
        onTrackClick={handleTrackClick}
        formatDuration={formatDuration}
      />
    </Container>
  );
};

export default AlbumDetailView;
