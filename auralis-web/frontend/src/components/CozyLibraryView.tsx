import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Grid,
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
  Star,
  FolderOpen,
  Refresh
} from '@mui/icons-material';
import AlbumCard from './library/AlbumCard';
import { LibraryGridSkeleton, TrackRowSkeleton } from './shared/SkeletonLoader';
import { useToast } from './shared/Toast';
import { usePlayerAPI } from '../hooks/usePlayerAPI';

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
  const [scanning, setScanning] = useState(false);
  const { success, error, info } = useToast();

  // Real player API for playback
  const { playTrack, setQueue } = usePlayerAPI();

  // Fetch tracks from API
  const fetchTracks = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/library/tracks?limit=100');
      if (response.ok) {
        const data = await response.json();
        setTracks(data.tracks || []);
        console.log('Loaded', data.tracks?.length || 0, 'tracks from library');
        if (data.tracks && data.tracks.length > 0) {
          success(`Loaded ${data.tracks.length} tracks`);
        }
      } else {
        console.error('Failed to fetch tracks');
        error('Failed to load library');
        // Fall back to mock data
        loadMockData();
      }
    } catch (err) {
      console.error('Error fetching tracks:', err);
      error('Failed to connect to server');
      // Fall back to mock data
      loadMockData();
    } finally {
      setLoading(false);
    }
  };

  // Check if running in Electron
  const isElectron = () => {
    return !!(window as any).electronAPI;
  };

  // Handle folder scan
  const handleScanFolder = async () => {
    let folderPath: string | undefined;

    // Use native folder picker in Electron
    if (isElectron()) {
      try {
        const result = await (window as any).electronAPI.selectFolder();
        if (result && result.length > 0) {
          folderPath = result[0];
        } else {
          return; // User cancelled
        }
      } catch (error) {
        console.error('Failed to open folder picker:', error);
        alert('❌ Failed to open folder picker');
        return;
      }
    } else {
      // Fallback to prompt in web browser
      folderPath = prompt('Enter folder path to scan:\n(e.g., /home/user/Music)') || undefined;
      if (!folderPath) return;
    }

    setScanning(true);
    try {
      const response = await fetch('http://localhost:8000/api/library/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directory: folderPath })
      });

      if (response.ok) {
        const result = await response.json();
        alert(`✅ Scan complete!\nAdded: ${result.files_added || 0} tracks`);
        // Refresh the library
        fetchTracks();
      } else {
        const error = await response.json();
        alert(`❌ Scan failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Scan error:', error);
      alert(`❌ Error scanning folder: ${error}`);
    } finally {
      setScanning(false);
    }
  };

  // Load mock data as fallback
  const loadMockData = () => {
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

    setTracks(mockTracks);
    setFilteredTracks(mockTracks);
  };

  // Initial load
  useEffect(() => {
    fetchTracks();
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

  // Use the new AlbumCard component

  const TrackListItem: React.FC<{ track: Track; index: number }> = ({ track, index }) => (
    <ListItem
      button
      onClick={async () => {
        // Play track using real backend player!
        await playTrack(track);
        success(`Now playing: ${track.title}`);
        // Also call parent callback if provided
        onTrackPlay?.(track);
      }}
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

          <Box sx={{ display: 'flex', gap: 1, ml: 'auto' }}>
            <Tooltip title="Scan Folder">
              <IconButton
                color="primary"
                onClick={handleScanFolder}
                disabled={scanning}
              >
                <FolderOpen />
              </IconButton>
            </Tooltip>

            <Tooltip title="Refresh Library">
              <IconButton
                onClick={fetchTracks}
                disabled={loading}
              >
                <Refresh />
              </IconButton>
            </Tooltip>

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

          <Typography variant="body2" color="text.secondary">
            {filteredTracks.length} songs
          </Typography>
        </Box>
      </Paper>

      {/* Music Grid/List */}
      {loading ? (
        viewMode === 'grid' ? (
          <LibraryGridSkeleton count={12} />
        ) : (
          <Paper
            elevation={2}
            sx={{
              background: 'rgba(255,255,255,0.05)',
              borderRadius: 3,
              overflow: 'hidden',
              p: 2
            }}
          >
            {Array.from({ length: 8 }).map((_, index) => (
              <TrackRowSkeleton key={index} />
            ))}
          </Paper>
        )
      ) : viewMode === 'grid' ? (
        <Grid container spacing={3}>
          {filteredTracks.map((track) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={track.id}>
              <AlbumCard
                id={track.id}
                title={track.album || track.title}
                artist={track.artist}
                albumArt={track.albumArt}
                onPlay={async (id) => {
                  const track = filteredTracks.find(t => t.id === id);
                  if (track) {
                    // Play track using real backend player!
                    await playTrack(track);
                    success(`Now playing: ${track.title}`);
                    // Also call parent callback if provided
                    onTrackPlay?.(track);
                  }
                }}
              />
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