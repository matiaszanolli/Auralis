import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Grid,
  Card,
  CardMedia,
  CardContent,
  Typography,
  TextField,
  InputAdornment,
  Chip,
  IconButton,
  Fade,
  Paper,
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Switch,
  FormControlLabel,
  Tooltip
} from '@mui/material';
import {
  Search,
  Album,
  MusicNote,
  PlayArrow,
  AutoAwesome,
  ViewModule,
  ViewList,
  FilterList,
  Star
} from '@mui/icons-material';

interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  albumArt?: string;
  quality?: number;
  isEnhanced?: boolean;
  genre?: string;
  year?: number;
}

interface CozyLibraryViewProps {
  onTrackPlay?: (track: Track) => void;
  onEnhancementToggle?: (trackId: number, enabled: boolean) => void;
}

const CozyLibraryView: React.FC<CozyLibraryViewProps> = ({
  onTrackPlay,
  onEnhancementToggle
}) => {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [filteredTracks, setFilteredTracks] = useState<Track[]>([]);

  // Mock data for demonstration (replace with API call)
  useEffect(() => {
    const mockTracks: Track[] = [
      {
        id: 1,
        title: "Bohemian Rhapsody",
        artist: "Queen",
        album: "A Night at the Opera",
        duration: 355,
        quality: 0.95,
        isEnhanced: true,
        genre: "Rock",
        year: 1975,
        albumArt: "https://via.placeholder.com/300x300/1976d2/white?text=Queen"
      },
      {
        id: 2,
        title: "Hotel California",
        artist: "Eagles",
        album: "Hotel California",
        duration: 391,
        quality: 0.88,
        isEnhanced: false,
        genre: "Rock",
        year: 1976,
        albumArt: "https://via.placeholder.com/300x300/d32f2f/white?text=Eagles"
      },
      {
        id: 3,
        title: "Billie Jean",
        artist: "Michael Jackson",
        album: "Thriller",
        duration: 294,
        quality: 0.92,
        isEnhanced: true,
        genre: "Pop",
        year: 1982,
        albumArt: "https://via.placeholder.com/300x300/388e3c/white?text=MJ"
      },
      {
        id: 4,
        title: "Sweet Child O' Mine",
        artist: "Guns N' Roses",
        album: "Appetite for Destruction",
        duration: 356,
        quality: 0.89,
        isEnhanced: false,
        genre: "Rock",
        year: 1987,
        albumArt: "https://via.placeholder.com/300x300/f57c00/white?text=GNR"
      }
    ];

    setTimeout(() => {
      setTracks(mockTracks);
      setFilteredTracks(mockTracks);
      setLoading(false);
    }, 500);
  }, []);

  // Filter tracks based on search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredTracks(tracks);
    } else {
      const filtered = tracks.filter(track =>
        track.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        track.artist.toLowerCase().includes(searchQuery.toLowerCase()) ||
        track.album.toLowerCase().includes(searchQuery.toLowerCase())
      );
      setFilteredTracks(filtered);
    }
  }, [searchQuery, tracks]);

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getQualityColor = (quality: number): string => {
    if (quality >= 0.9) return '#4caf50';
    if (quality >= 0.8) return '#ff9800';
    return '#f44336';
  };

  const AlbumCard: React.FC<{ track: Track }> = ({ track }) => (
    <Fade in timeout={300}>
      <Card
        elevation={4}
        sx={{
          height: '100%',
          background: 'linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%)',
          color: 'white',
          borderRadius: 3,
          overflow: 'hidden',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          '&:hover': {
            transform: 'translateY(-8px)',
            boxShadow: '0 12px 40px rgba(0,0,0,0.4)',
            '& .play-button': {
              opacity: 1,
              transform: 'scale(1)'
            }
          }
        }}
        onClick={() => onTrackPlay?.(track)}
      >
        <Box sx={{ position: 'relative' }}>
          <CardMedia
            component="img"
            height="200"
            image={track.albumArt}
            alt={track.album}
            sx={{
              transition: 'transform 0.3s ease'
            }}
          />

          {/* Play Button Overlay */}
          <IconButton
            className="play-button"
            sx={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%) scale(0.8)',
              opacity: 0,
              transition: 'all 0.3s ease',
              background: 'rgba(25,118,210,0.9)',
              color: 'white',
              width: 56,
              height: 56,
              '&:hover': {
                background: 'rgba(25,118,210,1)',
                transform: 'translate(-50%, -50%) scale(1.1)'
              }
            }}
          >
            <PlayArrow fontSize="large" />
          </IconButton>

          {/* Enhancement Badge */}
          {track.isEnhanced && (
            <Chip
              icon={<AutoAwesome />}
              label="Magic"
              size="small"
              sx={{
                position: 'absolute',
                top: 8,
                right: 8,
                background: 'linear-gradient(45deg, #1976d2, #42a5f5)',
                color: 'white',
                fontWeight: 'bold'
              }}
            />
          )}

          {/* Quality Indicator */}
          <Box
            sx={{
              position: 'absolute',
              bottom: 8,
              left: 8,
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              background: 'rgba(0,0,0,0.7)',
              borderRadius: 1,
              px: 1,
              py: 0.5
            }}
          >
            <Star sx={{ fontSize: 12, color: getQualityColor(track.quality || 0) }} />
            <Typography variant="caption" sx={{ color: 'white' }}>
              {Math.round((track.quality || 0) * 100)}%
            </Typography>
          </Box>
        </Box>

        <CardContent sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight="bold" noWrap>
            {track.title}
          </Typography>
          <Typography variant="body2" color="text.secondary" noWrap>
            {track.artist}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap>
            {track.album} • {track.year}
          </Typography>

          {/* Enhancement Toggle */}
          <Box sx={{ mt: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              {formatDuration(track.duration)}
            </Typography>
            <Tooltip title="Toggle Auralis Magic">
              <Switch
                size="small"
                checked={track.isEnhanced}
                onChange={(e) => {
                  e.stopPropagation();
                  onEnhancementToggle?.(track.id, e.target.checked);
                }}
                sx={{
                  '& .MuiSwitch-switchBase.Mui-checked': {
                    color: '#42a5f5'
                  },
                  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                    backgroundColor: '#1976d2'
                  }
                }}
              />
            </Tooltip>
          </Box>
        </CardContent>
      </Card>
    </Fade>
  );

  const TrackListItem: React.FC<{ track: Track; index: number }> = ({ track, index }) => (
    <ListItem
      button
      onClick={() => onTrackPlay?.(track)}
      sx={{
        borderRadius: 2,
        mb: 1,
        background: 'rgba(255,255,255,0.05)',
        '&:hover': {
          background: 'rgba(25,118,210,0.1)',
          transform: 'translateX(4px)'
        },
        transition: 'all 0.2s ease'
      }}
    >
      <ListItemAvatar>
        <Avatar
          src={track.albumArt}
          alt={track.album}
          sx={{ width: 56, height: 56, borderRadius: 2 }}
        />
      </ListItemAvatar>

      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle1" fontWeight="bold">
              {track.title}
            </Typography>
            {track.isEnhanced && (
              <Chip
                icon={<AutoAwesome />}
                label="Magic"
                size="small"
                color="primary"
                variant="outlined"
              />
            )}
          </Box>
        }
        secondary={
          <Typography variant="body2" color="text.secondary">
            {track.artist} • {track.album} • {formatDuration(track.duration)}
          </Typography>
        }
      />

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Star sx={{ fontSize: 16, color: getQualityColor(track.quality || 0) }} />
          <Typography variant="caption">
            {Math.round((track.quality || 0) * 100)}%
          </Typography>
        </Box>

        <Switch
          size="small"
          checked={track.isEnhanced}
          onChange={(e) => {
            e.stopPropagation();
            onEnhancementToggle?.(track.id, e.target.checked);
          }}
        />

        <IconButton color="primary">
          <PlayArrow />
        </IconButton>
      </Box>
    </ListItem>
  );

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography
          variant="h3"
          component="h1"
          fontWeight="bold"
          gutterBottom
          sx={{
            background: 'linear-gradient(45deg, #1976d2, #42a5f5)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}
        >
          🎵 Your Music Collection
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Rediscover the magic in every song
        </Typography>
      </Box>

      {/* Search and Controls */}
      <Paper
        elevation={2}
        sx={{
          p: 3,
          mb: 4,
          background: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(10px)',
          borderRadius: 3
        }}
      >
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Search your music..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
            sx={{
              maxWidth: 400,
              '& .MuiOutlinedInput-root': {
                borderRadius: 2
              }
            }}
          />

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Grid View">
              <IconButton
                color={viewMode === 'grid' ? 'primary' : 'default'}
                onClick={() => setViewMode('grid')}
              >
                <ViewModule />
              </IconButton>
            </Tooltip>

            <Tooltip title="List View">
              <IconButton
                color={viewMode === 'list' ? 'primary' : 'default'}
                onClick={() => setViewMode('list')}
              >
                <ViewList />
              </IconButton>
            </Tooltip>
          </Box>

          <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
            {filteredTracks.length} songs
          </Typography>
        </Box>
      </Paper>

      {/* Music Grid/List */}
      {viewMode === 'grid' ? (
        <Grid container spacing={3}>
          {filteredTracks.map((track) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={track.id}>
              <AlbumCard track={track} />
            </Grid>
          ))}
        </Grid>
      ) : (
        <Paper
          elevation={2}
          sx={{
            background: 'rgba(255,255,255,0.05)',
            borderRadius: 3,
            overflow: 'hidden'
          }}
        >
          <List sx={{ p: 2 }}>
            {filteredTracks.map((track, index) => (
              <TrackListItem key={track.id} track={track} index={index} />
            ))}
          </List>
        </Paper>
      )}

      {/* Empty State */}
      {filteredTracks.length === 0 && !loading && (
        <Paper
          elevation={2}
          sx={{
            p: 6,
            textAlign: 'center',
            background: 'rgba(255,255,255,0.05)',
            borderRadius: 3
          }}
        >
          <MusicNote sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No music found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {searchQuery ? 'Try adjusting your search terms' : 'Start by adding some music to your library'}
          </Typography>
        </Paper>
      )}
    </Container>
  );
};

export default CozyLibraryView;