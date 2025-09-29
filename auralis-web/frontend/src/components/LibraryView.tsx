import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Grid,
  Card,
  CardContent,
  Typography,
  TextField,
  InputAdornment,
  Fab,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button
} from '@mui/material';
import {
  Search as SearchIcon,
  FolderOpen as FolderOpenIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';

interface Track {
  id: number;
  title: string;
  filepath: string;
  duration?: number;
  format?: string;
  sample_rate?: number;
  channels?: number;
  artists?: string[];
  album?: string;
}

interface TracksResponse {
  tracks: Track[];
  total: number;
  offset: number;
  limit: number;
}

const LibraryView: React.FC = () => {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [scanDialogOpen, setScanDialogOpen] = useState(false);
  const [scanDirectory, setScanDirectory] = useState('');
  const [scanning, setScanning] = useState(false);

  const fetchTracks = async (search?: string) => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (search) params.append('search', search);

      const response = await fetch(`/api/library/tracks?${params}`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: TracksResponse = await response.json();
      setTracks(data.tracks);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch tracks';
      setError(errorMessage);
      console.error('Error fetching tracks:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    if (query.trim()) {
      fetchTracks(query);
    } else {
      fetchTracks();
    }
  };

  const handleScanDirectory = async () => {
    if (!scanDirectory.trim()) return;

    try {
      setScanning(true);
      const response = await fetch('/api/library/scan', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ directory: scanDirectory }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('Scan started:', result);

      setScanDialogOpen(false);
      setScanDirectory('');

      // Refresh tracks after scan
      setTimeout(() => {
        fetchTracks();
      }, 1000);

    } catch (err) {
      console.error('Error starting scan:', err);
    } finally {
      setScanning(false);
    }
  };

  const formatDuration = (seconds?: number): string => {
    if (!seconds) return 'Unknown';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'Unknown';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  useEffect(() => {
    fetchTracks();
  }, []);

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Grid container spacing={3}>
        {/* Header */}
        <Grid item xs={12}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
            <Typography variant="h4" component="h1">
              Music Library
            </Typography>
            <Box display="flex" gap={1}>
              <IconButton onClick={() => fetchTracks()} color="primary">
                <RefreshIcon />
              </IconButton>
            </Box>
          </Box>
        </Grid>

        {/* Search Bar */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Search tracks, artists, albums..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
            sx={{ mb: 2 }}
          />
        </Grid>

        {/* Content */}
        <Grid item xs={12}>
          {loading ? (
            <Box display="flex" justifyContent="center" py={4}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          ) : tracks.length === 0 ? (
            <Card>
              <CardContent sx={{ textAlign: 'center', py: 6 }}>
                <Typography variant="h6" color="text.secondary" gutterBottom>
                  No tracks found
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  {searchQuery
                    ? 'Try adjusting your search terms.'
                    : 'Start by scanning a directory containing audio files.'}
                </Typography>
                <Button
                  variant="contained"
                  startIcon={<FolderOpenIcon />}
                  onClick={() => setScanDialogOpen(true)}
                  sx={{ mt: 2 }}
                >
                  Scan Directory
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Tracks ({tracks.length})
                </Typography>
                <List>
                  {tracks.map((track) => (
                    <ListItem
                      key={track.id}
                      divider
                      sx={{
                        '&:hover': {
                          backgroundColor: 'action.hover',
                        },
                      }}
                    >
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={1}>
                            <Typography variant="subtitle1">
                              {track.title}
                            </Typography>
                            {track.format && (
                              <Chip
                                label={track.format.toUpperCase()}
                                size="small"
                                color="primary"
                                variant="outlined"
                              />
                            )}
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {track.artists?.join(', ') || 'Unknown Artist'}
                              {track.album && ` • ${track.album}`}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {formatDuration(track.duration)} • {track.sample_rate}Hz • {track.channels}ch
                              <br />
                              {track.filepath}
                            </Typography>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <IconButton edge="end" color="primary">
                          <PlayIcon />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>

      {/* Floating Action Button */}
      <Fab
        color="primary"
        aria-label="scan directory"
        sx={{
          position: 'fixed',
          bottom: 100, // Above audio player
          right: 16,
        }}
        onClick={() => setScanDialogOpen(true)}
      >
        <FolderOpenIcon />
      </Fab>

      {/* Scan Directory Dialog */}
      <Dialog open={scanDialogOpen} onClose={() => setScanDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Scan Directory for Audio Files</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Directory Path"
            fullWidth
            variant="outlined"
            value={scanDirectory}
            onChange={(e) => setScanDirectory(e.target.value)}
            placeholder="/path/to/your/music/folder"
            helperText="Enter the full path to a directory containing audio files"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setScanDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleScanDirectory}
            variant="contained"
            disabled={!scanDirectory.trim() || scanning}
          >
            {scanning ? <CircularProgress size={20} /> : 'Scan'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default LibraryView;