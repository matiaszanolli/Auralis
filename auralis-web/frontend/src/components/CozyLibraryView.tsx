import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Grid,
  Typography,
  IconButton,
  Paper,
  Tooltip
} from '@mui/material';
import {
  MusicNote,
  FolderOpen,
  Refresh
} from '@mui/icons-material';
import AlbumCard from './library/AlbumCard';
import TrackRow from './library/TrackRow';
import TrackQueue from './player/TrackQueue';
import SearchBar from './navigation/SearchBar';
import ViewToggle, { ViewMode } from './navigation/ViewToggle';
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
  view?: string;
}

const CozyLibraryView: React.FC<CozyLibraryViewProps> = ({
  onTrackPlay,
  view = 'songs'
}) => {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [filteredTracks, setFilteredTracks] = useState<Track[]>([]);
  const [scanning, setScanning] = useState(false);
  const [currentTrackId, setCurrentTrackId] = useState<number | undefined>(undefined);
  const [isPlaying, setIsPlaying] = useState(false);
  const { success, error, info } = useToast();

  // Real player API for playback
  const { playTrack, setQueue } = usePlayerAPI();

  // Fetch tracks from API
  const fetchTracks = async () => {
    setLoading(true);
    try {
      // Determine which endpoint to use based on view
      const endpoint = view === 'favourites'
        ? 'http://localhost:8765/api/library/tracks/favorites'
        : 'http://localhost:8765/api/library/tracks?limit=100';

      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();
        setTracks(data.tracks || []);
        console.log('Loaded', data.tracks?.length || 0, view === 'favourites' ? 'favorite tracks' : 'tracks from library');
        if (data.tracks && data.tracks.length > 0) {
          success(`Loaded ${data.tracks.length} ${view === 'favourites' ? 'favorites' : 'tracks'}`);
        } else if (view === 'favourites') {
          info('No favorites yet. Click the heart icon on tracks to add them!');
        }
      } else {
        console.error('Failed to fetch tracks');
        error('Failed to load library');
        // Fall back to mock data only for regular view
        if (view !== 'favourites') {
          loadMockData();
        }
      }
    } catch (err) {
      console.error('Error fetching tracks:', err);
      error('Failed to connect to server');
      // Fall back to mock data only for regular view
      if (view !== 'favourites') {
        loadMockData();
      }
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
      const response = await fetch('http://localhost:8765/api/library/scan', {
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

  // Initial load and reload when view changes
  useEffect(() => {
    fetchTracks();
  }, [view]);

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

  // Handler for playing a track
  const handlePlayTrack = async (track: Track) => {
    await playTrack(track);
    setCurrentTrackId(track.id);
    setIsPlaying(true);
    success(`Now playing: ${track.title}`);
    onTrackPlay?.(track);
  };

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
          {view === 'favourites' ? '❤️ Your Favorites' : '🎵 Your Music Collection'}
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          {view === 'favourites' ? 'Your most loved tracks' : 'Rediscover the magic in every song'}
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
          <Box sx={{ maxWidth: 400, flex: 1 }}>
            <SearchBar
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search your music..."
            />
          </Box>

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

            <ViewToggle value={viewMode} onChange={setViewMode} />
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
        <>
          <Grid container spacing={3}>
            {filteredTracks.map((track, index) => (
              <Grid
                item
                xs={12}
                sm={6}
                md={4}
                lg={3}
                key={track.id}
                className="animate-fade-in-up"
                sx={{
                  animationDelay: `${index * 0.05}s`,
                  animationFillMode: 'both'
                }}
              >
                <AlbumCard
                  id={track.id}
                  title={track.album || track.title}
                  artist={track.artist}
                  albumArt={track.albumArt}
                  onPlay={async (id) => {
                    const track = filteredTracks.find(t => t.id === id);
                    if (track) {
                      await handlePlayTrack(track);
                    }
                  }}
                />
              </Grid>
            ))}
          </Grid>

          {/* Track Queue - Shows current album/playlist tracks */}
          {filteredTracks.length > 0 && (
            <TrackQueue
              tracks={filteredTracks.map(t => ({
                id: t.id,
                title: t.title,
                artist: t.artist,
                duration: t.duration
              }))}
              currentTrackId={currentTrackId}
              onTrackClick={(trackId) => {
                const track = filteredTracks.find(t => t.id === trackId);
                if (track) {
                  handlePlayTrack(track);
                }
              }}
              title="Current Queue"
            />
          )}
        </>
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
          {filteredTracks.map((track, index) => (
            <Box
              key={track.id}
              className="animate-fade-in-left"
              sx={{
                animationDelay: `${index * 0.03}s`,
                animationFillMode: 'both'
              }}
            >
              <TrackRow
                track={track}
                index={index}
                isPlaying={isPlaying}
                isCurrent={currentTrackId === track.id}
                onPlay={(trackId) => {
                  const track = filteredTracks.find(t => t.id === trackId);
                  if (track) {
                    handlePlayTrack(track);
                  }
                }}
                onPause={() => setIsPlaying(false)}
              />
            </Box>
          ))}
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
            {view === 'favourites' ? 'No favorites yet' : 'No music found'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {view === 'favourites'
              ? 'Click the heart icon on tracks you love to add them to your favorites'
              : searchQuery
                ? 'Try adjusting your search terms'
                : 'Start by adding some music to your library'}
          </Typography>
        </Paper>
      )}
    </Container>
  );
};

export default CozyLibraryView;