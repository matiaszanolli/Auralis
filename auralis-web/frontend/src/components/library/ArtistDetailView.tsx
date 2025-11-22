import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  IconButton,
  Button,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Skeleton,
  Tabs,
  Tab,
  Divider
} from '@mui/material';
import {
  ArrowBack,
  PlayArrow,
  Pause,
  Shuffle,
  MoreVert
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import AlbumArt from '../album/AlbumArt';
import { EmptyStateBox } from './EmptyStateBox';
import DetailViewHeader from './DetailViewHeader';
import { PlayButton, ShuffleButton } from './Button.styles';
import { StyledTableRow, PlayIcon } from './Table.styles';

interface Track {
  id: number;
  title: string;
  album: string;
  duration: number;
  track_number?: number;
}

interface Album {
  id: number;
  title: string;
  year?: number;
  track_count: number;
  total_duration: number;
}

interface Artist {
  id: number;
  name: string;
  album_count?: number;
  track_count?: number;
  albums?: Album[];
  tracks?: Track[];
}

interface ArtistDetailViewProps {
  artistId: number;
  artistName?: string;
  onBack?: () => void;
  onTrackPlay?: (track: Track) => void;
  onAlbumClick?: (albumId: number) => void;
  currentTrackId?: number;
  isPlaying?: boolean;
}

// Styled Components

const AlbumCard = styled(Paper)(({ theme }) => ({
  background: 'rgba(255,255,255,0.03)',
  borderRadius: theme.spacing(2),
  overflow: 'hidden',
  cursor: 'pointer',
  transition: 'all 0.2s ease',
  border: '1px solid rgba(255,255,255,0.05)',
  '&:hover': {
    transform: 'translateY(-4px)',
    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
    '& .album-title': {
      color: '#667eea'
    }
  }
}));

const AlbumTitle = styled(Typography)(({ theme }) => ({
  fontSize: '1rem',
  fontWeight: 600,
  color: theme.palette.text.primary,
  marginBottom: 4,
  transition: 'color 0.2s ease'
}));

const AlbumInfo = styled(Typography)(({ theme }) => ({
  fontSize: '0.875rem',
  color: theme.palette.text.secondary
}));


const StyledTabs = styled(Tabs)(({ theme }) => ({
  borderBottom: '1px solid rgba(255,255,255,0.1)',
  marginBottom: theme.spacing(3),
  '& .MuiTab-root': {
    textTransform: 'none',
    fontSize: '1rem',
    fontWeight: 500,
    minWidth: 120,
    '&.Mui-selected': {
      color: '#667eea'
    }
  },
  '& .MuiTabs-indicator': {
    backgroundColor: '#667eea'
  }
}));

export const ArtistDetailView: React.FC<ArtistDetailViewProps> = ({
  artistId,
  artistName,
  onBack,
  onTrackPlay,
  onAlbumClick,
  currentTrackId,
  isPlaying = false
}) => {
  const [artist, setArtist] = useState<Artist | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    fetchArtistDetails();
  }, [artistId]);

  const fetchArtistDetails = async () => {
    setLoading(true);
    setError(null);

    try {
      // Use new REST API endpoint for artist details
      const response = await fetch(`/api/artists/${artistId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch artist details');
      }

      const data = await response.json();

      // Transform API response to match Artist interface
      const artistData: Artist = {
        id: data.artist_id,
        name: data.artist_name,
        album_count: data.total_albums,
        track_count: data.total_tracks,
        albums: data.albums || [],
        tracks: [] // Tracks loaded separately if needed
      };

      setArtist(artistData);
    } catch (err) {
      console.error('Error fetching artist details:', err);
      setError(err instanceof Error ? err.message : 'Failed to load artist details');
    } finally {
      setLoading(false);
    }
  };

  const getArtistInitial = (name: string): string => {
    return name.charAt(0).toUpperCase();
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
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

  const handlePlayAll = () => {
    if (artist?.tracks && artist.tracks.length > 0 && onTrackPlay) {
      onTrackPlay(artist.tracks[0]);
    }
  };

  const handleShufflePlay = () => {
    if (artist?.tracks && artist.tracks.length > 0 && onTrackPlay) {
      const randomIndex = Math.floor(Math.random() * artist.tracks.length);
      onTrackPlay(artist.tracks[randomIndex]);
    }
  };

  const handleTrackClick = (track: Track) => {
    if (onTrackPlay) {
      onTrackPlay(track);
    }
  };

  const handleAlbumCardClick = (albumId: number) => {
    if (onAlbumClick) {
      onAlbumClick(albumId);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 2, mb: 4 }} />
        <Skeleton variant="rectangular" height={400} sx={{ borderRadius: 2 }} />
      </Container>
    );
  }

  if (error || !artist) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <EmptyStateBox
          title={error ? 'Error Loading Artist' : 'Artist not found'}
          subtitle={error || undefined}
        />
        {onBack && (
          <Box sx={{ textAlign: 'center', mt: 2 }}>
            <Button onClick={onBack} startIcon={<ArrowBack />}>
              Back to Artists
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
              backgroundColor: 'rgba(255,255,255,0.1)'
            }
          }}
        >
          <ArrowBack />
        </IconButton>
      )}

      {/* Artist Header */}
      <DetailViewHeader
        artwork={
          <Box
            sx={{
              width: 200,
              height: 200,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '5rem',
              fontWeight: 'bold',
              color: 'white',
              boxShadow: '0 8px 32px rgba(102, 126, 234, 0.3)',
            }}
          >
            {getArtistInitial(artist.name)}
          </Box>
        }
        title={artist.name}
        metadata={
          <Typography variant="body1" sx={{ color: 'text.secondary' }}>
            {artist.album_count && `${artist.album_count} ${artist.album_count === 1 ? 'album' : 'albums'}`}
            {artist.album_count && artist.track_count && ' • '}
            {artist.track_count && `${artist.track_count} ${artist.track_count === 1 ? 'track' : 'tracks'}`}
          </Typography>
        }
        actions={
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <PlayButton
              startIcon={<PlayArrow />}
              onClick={handlePlayAll}
            >
              Play All
            </PlayButton>

            <ShuffleButton
              variant="outlined"
              startIcon={<Shuffle />}
              onClick={handleShufflePlay}
            >
              Shuffle
            </ShuffleButton>

            <IconButton
              sx={{
                '&:hover': {
                  backgroundColor: 'rgba(255,255,255,0.1)'
                }
              }}
            >
              <MoreVert />
            </IconButton>
          </Box>
        }
      />

      {/* Tabs for Albums and Tracks */}
      <Box>
        <StyledTabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label={`Albums (${artist.albums?.length || 0})`} />
          <Tab label={`All Tracks (${artist.tracks?.length || 0})`} />
        </StyledTabs>

        {/* Albums Tab */}
        {activeTab === 0 && (
          <Box>
            {artist.albums && artist.albums.length > 0 ? (
              <Grid container spacing={3}>
                {artist.albums.map((album) => (
                  <Grid item xs={12} sm={6} md={4} lg={3} xl={2} key={album.id}>
                    <AlbumCard onClick={() => handleAlbumCardClick(album.id)}>
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
            ) : (
              <Paper
                sx={{
                  p: 4,
                  textAlign: 'center',
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: 2
                }}
              >
                <Typography color="text.secondary">
                  No albums found for this artist
                </Typography>
              </Paper>
            )}
          </Box>
        )}

        {/* All Tracks Tab */}
        {activeTab === 1 && (
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
                    Album
                  </TableCell>
                  <TableCell align="right" width="100px" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
                    Duration
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {artist.tracks && artist.tracks.length > 0 ? (
                  artist.tracks.map((track, index) => (
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
                                sx={{
                                  fontSize: '0.9rem',
                                  color: 'text.secondary',
                                  '.current-track &': { display: 'none' }
                                }}
                              >
                                {index + 1}
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
                          {track.album}
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
                        No tracks found for this artist
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
    </Container>
  );
};

export default ArtistDetailView;
