import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  IconButton,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Skeleton,
  Tooltip
} from '@mui/material';
import {
  ArrowBack,
  PlayArrow,
  Pause,
  AddToQueue,
  MoreVert,
  Favorite,
  FavoriteBorder
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
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

// Styled Components
const HeaderSection = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(4),
  marginBottom: theme.spacing(4),
  padding: theme.spacing(4),
  background: 'rgba(255,255,255,0.03)',
  borderRadius: theme.spacing(2),
  backdropFilter: 'blur(10px)',
  border: '1px solid rgba(255,255,255,0.05)'
}));

const AlbumArtWrapper = styled(Box)({
  flexShrink: 0,
  width: 280,
  height: 280,
  borderRadius: 12,
  overflow: 'hidden',
  boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
});

const AlbumInfo = styled(Box)(({ theme }) => ({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  gap: theme.spacing(2)
}));

const AlbumTitle = styled(Typography)({
  fontSize: '2.5rem',
  fontWeight: 'bold',
  background: 'linear-gradient(45deg, #667eea, #764ba2)',
  backgroundClip: 'text',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  marginBottom: 8
});

const AlbumArtist = styled(Typography)(({ theme }) => ({
  fontSize: '1.5rem',
  color: theme.palette.text.secondary,
  marginBottom: 16
}));

const AlbumMetadata = styled(Typography)(({ theme }) => ({
  fontSize: '0.95rem',
  color: theme.palette.text.secondary,
  marginBottom: 4
}));

const ActionButtons = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(2),
  marginTop: theme.spacing(2)
}));

const PlayButton = styled(Button)(({ theme }) => ({
  background: 'linear-gradient(45deg, #667eea, #764ba2)',
  color: 'white',
  padding: '12px 32px',
  fontSize: '1rem',
  fontWeight: 'bold',
  borderRadius: 24,
  textTransform: 'none',
  '&:hover': {
    background: 'linear-gradient(45deg, #5568d3, #6a3f8f)',
    transform: 'translateY(-2px)',
    boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)'
  },
  transition: 'all 0.2s ease'
}));

const StyledTableRow = styled(TableRow)(({ theme }) => ({
  cursor: 'pointer',
  transition: 'background-color 0.2s ease',
  '&:hover': {
    backgroundColor: 'rgba(255,255,255,0.05)',
    '& .play-icon': {
      opacity: 1
    }
  },
  '&.current-track': {
    backgroundColor: 'rgba(102, 126, 234, 0.15)',
    '& .track-number': {
      color: '#667eea'
    },
    '& .track-title': {
      color: '#667eea',
      fontWeight: 'bold'
    }
  }
}));

const PlayIcon = styled(Box)({
  opacity: 0,
  transition: 'opacity 0.2s ease',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center'
});

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

  const toggleFavorite = () => {
    setIsFavorite(!isFavorite);
    // TODO: Call API to update favorite status
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
        <Paper
          elevation={2}
          sx={{
            p: 6,
            textAlign: 'center',
            background: 'rgba(255,255,255,0.05)',
            borderRadius: 3
          }}
        >
          <Typography variant="h6" color="error" gutterBottom>
            {error || 'Album not found'}
          </Typography>
          {onBack && (
            <Button onClick={onBack} startIcon={<ArrowBack />} sx={{ mt: 2 }}>
              Back to Albums
            </Button>
          )}
        </Paper>
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
              backgroundColor: 'rgba(255,255,255,0.1)'
            }
          }}
        >
          <ArrowBack />
        </IconButton>
      )}

      {/* Album Header */}
      <HeaderSection>
        <AlbumArtWrapper>
          <AlbumArt
            albumId={album.id}
            size={280}
            borderRadius={0}
          />
        </AlbumArtWrapper>

        <AlbumInfo>
          <Box>
            <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 1 }}>
              Album
            </Typography>
            <AlbumTitle variant="h2">
              {album.title}
            </AlbumTitle>
            <AlbumArtist variant="h5">
              {album.artist_name || album.artist}
            </AlbumArtist>
          </Box>

          <Box>
            <AlbumMetadata>
              {album.year && `${album.year} • `}
              {album.track_count} {album.track_count === 1 ? 'track' : 'tracks'}
              {' • '}
              {formatTotalDuration(album.total_duration)}
            </AlbumMetadata>
            {album.genre && (
              <AlbumMetadata>
                Genre: {album.genre}
              </AlbumMetadata>
            )}
          </Box>

          <ActionButtons>
            <PlayButton
              startIcon={isPlaying && currentTrackId === album.tracks?.[0]?.id ? <Pause /> : <PlayArrow />}
              onClick={handlePlayAlbum}
            >
              {isPlaying && currentTrackId === album.tracks?.[0]?.id ? 'Pause' : 'Play Album'}
            </PlayButton>

            <Tooltip title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}>
              <IconButton
                onClick={toggleFavorite}
                sx={{
                  color: isFavorite ? '#f50057' : 'text.secondary',
                  '&:hover': {
                    backgroundColor: 'rgba(255,255,255,0.1)'
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
                    backgroundColor: 'rgba(255,255,255,0.1)'
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
                    backgroundColor: 'rgba(255,255,255,0.1)'
                  }
                }}
              >
                <MoreVert />
              </IconButton>
            </Tooltip>
          </ActionButtons>
        </AlbumInfo>
      </HeaderSection>

      {/* Track Listing */}
      <TableContainer
        component={Paper}
        elevation={2}
        sx={{
          background: 'rgba(255,255,255,0.03)',
          borderRadius: 2,
          backdropFilter: 'blur(10px)'
        }}
      >
        <Table>
          <TableHead>
            <TableRow>
              <TableCell width="60px" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
                #
              </TableCell>
              <TableCell sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
                Title
              </TableCell>
              <TableCell sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
                Artist
              </TableCell>
              <TableCell align="right" width="100px" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
                Duration
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {album.tracks && album.tracks.length > 0 ? (
              album.tracks.map((track, index) => (
                <StyledTableRow
                  key={track.id}
                  onClick={() => handleTrackClick(track)}
                  className={currentTrackId === track.id ? 'current-track' : ''}
                >
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {currentTrackId === track.id && isPlaying ? (
                        <Pause sx={{ fontSize: 20, color: '#667eea' }} />
                      ) : (
                        <>
                          <Typography
                            className="track-number"
                            sx={{
                              fontSize: '0.9rem',
                              color: 'text.secondary',
                              '.current-track &': { display: 'none' }
                            }}
                          >
                            {track.track_number || index + 1}
                          </Typography>
                          <PlayIcon className="play-icon">
                            <PlayArrow sx={{ fontSize: 20 }} />
                          </PlayIcon>
                        </>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography
                      className="track-title"
                      sx={{
                        fontSize: '0.95rem',
                        fontWeight: currentTrackId === track.id ? 'bold' : 'normal'
                      }}
                    >
                      {track.title}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary' }}>
                      {track.artist}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary' }}>
                      {formatDuration(track.duration)}
                    </Typography>
                  </TableCell>
                </StyledTableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    No tracks found for this album
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
};

export default AlbumDetailView;
