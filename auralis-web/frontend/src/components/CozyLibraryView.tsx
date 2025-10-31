import React, { useState, useEffect, useRef, useCallback } from 'react';
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
import AlbumArt from './album/AlbumArt';
import TrackRow from './library/TrackRow';
import SelectableTrackRow from './library/SelectableTrackRow';
import BatchActionsToolbar from './library/BatchActionsToolbar';
import EnhancedTrackQueue from './player/EnhancedTrackQueue';
import SearchBar from './navigation/SearchBar';
import ViewToggle, { ViewMode } from './navigation/ViewToggle';
import { LibraryGridSkeleton, TrackRowSkeleton } from './shared/SkeletonLoader';
import { useToast } from './shared/Toast';
import { EmptyLibrary, NoSearchResults, EmptyState } from './shared/EmptyState';
import { usePlayerAPI } from '../hooks/usePlayerAPI';
import { useTrackSelection } from '../hooks/useTrackSelection';
import * as queueService from '../services/queueService';
import { CozyAlbumGrid } from './library/CozyAlbumGrid';
import { CozyArtistList } from './library/CozyArtistList';
import AlbumDetailView from './library/AlbumDetailView';
import ArtistDetailView from './library/ArtistDetailView';
import EditMetadataDialog from './library/EditMetadataDialog';

interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  album_id?: number;
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
  const [selectedAlbumId, setSelectedAlbumId] = useState<number | null>(null);
  const [selectedArtistId, setSelectedArtistId] = useState<number | null>(null);
  const [selectedArtistName, setSelectedArtistName] = useState<string>('');
  const [editMetadataDialogOpen, setEditMetadataDialogOpen] = useState(false);
  const [editingTrackId, setEditingTrackId] = useState<number | null>(null);

  // Pagination state
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [totalTracks, setTotalTracks] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const { success, error, info } = useToast();

  // Real player API for playback
  const { playTrack, setQueue } = usePlayerAPI();

  // Track selection for batch operations
  const {
    selectedTracks,
    isSelected,
    toggleTrack,
    selectAll,
    clearSelection,
    selectedCount,
    hasSelection
  } = useTrackSelection(filteredTracks);

  // Ref for infinite scroll observer
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Fetch tracks from API with pagination
  const fetchTracks = async (resetPagination = true) => {
    setLoading(true);
    if (resetPagination) {
      setOffset(0);
      setTracks([]);
    }

    try {
      const limit = 50;
      const currentOffset = resetPagination ? 0 : offset;

      // Determine which endpoint to use based on view
      const endpoint = view === 'favourites'
        ? `http://localhost:8765/api/library/tracks/favorites?limit=${limit}&offset=${currentOffset}`
        : `http://localhost:8765/api/library/tracks?limit=${limit}&offset=${currentOffset}`;

      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();

        // Update state with pagination info
        setHasMore(data.has_more || false);
        setTotalTracks(data.total || 0);

        if (resetPagination) {
          setTracks(data.tracks || []);
        } else {
          setTracks(prev => [...prev, ...(data.tracks || [])]);
        }

        console.log('Loaded', data.tracks?.length || 0, view === 'favourites' ? 'favorite tracks' : 'tracks from library');
        console.log(`Pagination: ${currentOffset + (data.tracks?.length || 0)}/${data.total || 0}, has_more: ${data.has_more}`);

        if (resetPagination && data.tracks && data.tracks.length > 0) {
          success(`Loaded ${data.tracks.length} of ${data.total} ${view === 'favourites' ? 'favorites' : 'tracks'}`);
        } else if (resetPagination && view === 'favourites') {
          info('No favorites yet. Click the heart icon on tracks to add them!');
        }
      } else {
        console.error('Failed to fetch tracks');
        error('Failed to load library');
        // Fall back to mock data only for regular view
        if (view !== 'favourites' && resetPagination) {
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

  // Load more tracks (for infinite scroll)
  const loadMore = async () => {
    if (isLoadingMore || !hasMore) {
      return;
    }

    setIsLoadingMore(true);
    try {
      const limit = 50;
      const newOffset = offset + limit;
      setOffset(newOffset);

      const endpoint = view === 'favourites'
        ? `http://localhost:8765/api/library/tracks/favorites?limit=${limit}&offset=${newOffset}`
        : `http://localhost:8765/api/library/tracks?limit=${limit}&offset=${newOffset}`;

      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();

        // Append new tracks
        setTracks(prev => [...prev, ...(data.tracks || [])]);
        setHasMore(data.has_more || false);
        setTotalTracks(data.total || 0);

        console.log(`Loaded more: ${newOffset + (data.tracks?.length || 0)}/${data.total || 0}`);
      }
    } catch (err) {
      console.error('Error loading more tracks:', err);
    } finally {
      setIsLoadingMore(false);
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

  // Reset selected album/artist when view changes (fixes sidebar navigation from detail views)
  useEffect(() => {
    setSelectedAlbumId(null);
    setSelectedArtistId(null);
    setSelectedArtistName('');
  }, [view]);

  // Selection keyboard shortcuts (Ctrl+A, Escape)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't handle if typing in input field
      const target = event.target as HTMLElement;
      const isInput = target.tagName.toLowerCase() === 'input' ||
                     target.tagName.toLowerCase() === 'textarea' ||
                     target.contentEditable === 'true';

      if (isInput) return;

      // Ctrl/Cmd + A: Select all tracks
      if ((event.ctrlKey || event.metaKey) && event.key === 'a' && filteredTracks.length > 0) {
        event.preventDefault();
        selectAll();
        info(`Selected all ${filteredTracks.length} tracks`);
      }

      // Escape: Clear selection (if tracks are selected)
      if (event.key === 'Escape' && hasSelection) {
        event.preventDefault();
        clearSelection();
        info('Selection cleared');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [filteredTracks, hasSelection, selectAll, clearSelection, info]);

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

  // Infinite scroll with Intersection Observer
  useEffect(() => {
    if (!loadMoreRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoadingMore && !loading) {
          loadMore();
        }
      },
      { threshold: 0.1 } // Lower threshold to trigger earlier
    );

    observer.observe(loadMoreRef.current);

    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, loading, loadMore]);

  const formatDuration = (seconds: number): string => {
    const totalSeconds = Math.floor(seconds); // Round to integer first
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
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

  // Handler for editing track metadata
  const handleEditMetadata = (trackId: number) => {
    setEditingTrackId(trackId);
    setEditMetadataDialogOpen(true);
  };

  // Batch action handlers
  const handleBulkAddToQueue = async () => {
    try {
      const selectedTrackIds = Array.from(selectedTracks);
      for (const trackId of selectedTrackIds) {
        await fetch('http://localhost:8765/api/player/queue/add-track', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ track_id: trackId })
        });
      }
      success(`Added ${selectedCount} tracks to queue`);
      clearSelection();
    } catch (err) {
      error('Failed to add tracks to queue');
    }
  };

  const handleBulkAddToPlaylist = async () => {
    // TODO: Show playlist selection dialog
    info('Bulk add to playlist - Coming soon!');
    // For now, just show a message
    // Future: Open dialog to select playlist, then bulk add
  };

  const handleBulkRemove = async () => {
    if (!confirm(`Remove ${selectedCount} tracks?`)) {
      return;
    }

    try {
      // Context-dependent removal
      if (view === 'favorites') {
        // Remove from favorites
        for (const trackId of selectedTracks) {
          await fetch(`http://localhost:8765/api/library/tracks/${trackId}/favorite`, {
            method: 'DELETE'
          });
        }
        success(`Removed ${selectedCount} tracks from favorites`);
      } else {
        // Remove from library (requires confirmation)
        info('Bulk delete from library requires API implementation');
      }

      clearSelection();
      fetchTracks(); // Refresh
    } catch (err) {
      error('Failed to remove tracks');
    }
  };

  const handleBulkToggleFavorite = async () => {
    try {
      for (const trackId of selectedTracks) {
        await fetch(`http://localhost:8765/api/library/tracks/${trackId}/favorite`, {
          method: 'POST'
        });
      }
      success(`Toggled favorite for ${selectedCount} tracks`);
      clearSelection();
      fetchTracks(); // Refresh
    } catch (err) {
      error('Failed to toggle favorites');
    }
  };

  // Show album detail view (can come from albums view or artist view)
  if (selectedAlbumId !== null) {
    return (
      <AlbumDetailView
        albumId={selectedAlbumId}
        onBack={() => {
          setSelectedAlbumId(null);
          // If we came from artist view, go back to artist detail
          if (view === 'artists' && selectedArtistId !== null) {
            // Stay in artist detail view
          }
        }}
        onTrackPlay={handlePlayTrack}
        currentTrackId={currentTrackId}
        isPlaying={isPlaying}
      />
    );
  }

  // Show album grid view
  if (view === 'albums') {

    // Otherwise show album grid
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Box sx={{ mb: 4 }}>
          <Typography
            variant="h3"
            component="h1"
            fontWeight="bold"
            gutterBottom
            sx={{
              background: 'linear-gradient(45deg, #667eea, #764ba2)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}
          >
            📀 Albums
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            Browse your music collection by album
          </Typography>
        </Box>
        <CozyAlbumGrid onAlbumClick={(albumId) => setSelectedAlbumId(albumId)} />
      </Container>
    );
  }

  // Show artist list view
  if (view === 'artists') {
    // If an artist is selected, show detail view
    if (selectedArtistId !== null) {
      return (
        <ArtistDetailView
          artistId={selectedArtistId}
          artistName={selectedArtistName}
          onBack={() => {
            setSelectedArtistId(null);
            setSelectedArtistName('');
          }}
          onTrackPlay={handlePlayTrack}
          onAlbumClick={(albumId) => {
            // Navigate to album detail view
            setSelectedAlbumId(albumId);
          }}
          currentTrackId={currentTrackId}
          isPlaying={isPlaying}
        />
      );
    }

    // Otherwise show artist list
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Box sx={{ mb: 4 }}>
          <Typography
            variant="h3"
            component="h1"
            fontWeight="bold"
            gutterBottom
            sx={{
              background: 'linear-gradient(45deg, #667eea, #764ba2)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}
          >
            🎤 Artists
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            Browse artists in your music library
          </Typography>
        </Box>
        <CozyArtistList
          onArtistClick={(artistId, artistName) => {
            setSelectedArtistId(artistId);
            setSelectedArtistName(artistName);
          }}
        />
      </Container>
    );
  }

  return (
    <>
      {/* Batch Actions Toolbar - Appears when tracks selected */}
      {hasSelection && (
        <BatchActionsToolbar
          selectedCount={selectedCount}
          onAddToQueue={handleBulkAddToQueue}
          onAddToPlaylist={handleBulkAddToPlaylist}
          onRemove={handleBulkRemove}
          onToggleFavorite={handleBulkToggleFavorite}
          onClearSelection={clearSelection}
          context={view === 'favourites' ? 'favorites' : 'library'}
        />
      )}

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
                  title={track.title}
                  artist={track.artist}
                  albumId={track.album_id}
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

          {/* Intersection observer trigger for infinite scroll */}
          {hasMore && (
            <Box
              ref={loadMoreRef}
              sx={{
                height: '1px',
                width: '100%',
                pointerEvents: 'auto'
              }}
            />
          )}

          {/* Virtual spacer for proper scrollbar length in grid view */}
          {hasMore && totalTracks > tracks.length && (
            <Box
              sx={{
                height: `${Math.ceil((totalTracks - tracks.length) / 4) * 240}px`, // 4 cols (lg), ~240px per row
                pointerEvents: 'none'
              }}
            />
          )}

          {/* Track Queue - Shows current album/playlist tracks */}
          {filteredTracks.length > 0 && (
            <EnhancedTrackQueue
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
              onRemoveTrack={async (index) => {
                try {
                  await queueService.removeTrackFromQueue(index);
                  info('Track removed from queue');
                  // Refresh tracks to reflect queue changes
                  fetchTracks();
                } catch (err) {
                  error('Failed to remove track from queue');
                }
              }}
              onReorderQueue={async (newOrder) => {
                try {
                  await queueService.reorderQueue(newOrder);
                  success('Queue reordered');
                  // Refresh tracks to reflect queue changes
                  fetchTracks();
                } catch (err) {
                  error('Failed to reorder queue');
                }
              }}
              onShuffleQueue={async () => {
                try {
                  await queueService.shuffleQueue();
                  success('Queue shuffled');
                  // Refresh tracks to reflect queue changes
                  fetchTracks();
                } catch (err) {
                  error('Failed to shuffle queue');
                }
              }}
              onClearQueue={async () => {
                try {
                  await queueService.clearQueue();
                  info('Queue cleared');
                  // Refresh tracks to reflect queue changes
                  fetchTracks();
                } catch (err) {
                  error('Failed to clear queue');
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
              <SelectableTrackRow
                track={track}
                index={index}
                isSelected={isSelected(track.id)}
                onToggleSelect={(e) => toggleTrack(track.id, e)}
                isPlaying={isPlaying}
                isCurrent={currentTrackId === track.id}
                onPlay={(trackId) => {
                  const track = filteredTracks.find(t => t.id === trackId);
                  if (track) {
                    handlePlayTrack(track);
                  }
                }}
                onPause={() => setIsPlaying(false)}
                onEditMetadata={handleEditMetadata}
              />
            </Box>
          ))}

          {/* Intersection observer trigger for infinite scroll */}
          {hasMore && (
            <Box
              ref={loadMoreRef}
              sx={{
                height: '1px',
                width: '100%',
                pointerEvents: 'auto'
              }}
            />
          )}

          {/* Virtual spacer for proper scrollbar length */}
          {hasMore && totalTracks > tracks.length && (
            <Box
              sx={{
                height: `${(totalTracks - tracks.length) * 72}px`, // 72px avg row height
                pointerEvents: 'none'
              }}
            />
          )}

          {/* Infinite scroll loading indicator */}
          {isLoadingMore && (
            <Box
              sx={{
                p: 3,
                textAlign: 'center',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 2
              }}
            >
              <Box
                sx={{
                  width: 20,
                  height: 20,
                  border: '2px solid',
                  borderColor: 'primary.main',
                  borderRightColor: 'transparent',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                  '@keyframes spin': {
                    '0%': { transform: 'rotate(0deg)' },
                    '100%': { transform: 'rotate(360deg)' }
                  }
                }}
              />
              <Typography variant="body2" color="text.secondary">
                Loading more tracks... ({tracks.length}/{totalTracks})
              </Typography>
            </Box>
          )}

          {/* End of list indicator */}
          {!hasMore && tracks.length > 0 && (
            <Box sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                Showing all {totalTracks} tracks
              </Typography>
            </Box>
          )}
        </Paper>
      )}

      {/* Empty State */}
      {filteredTracks.length === 0 && !loading && (
        <>
          {view === 'favourites' ? (
            <EmptyState
              icon="music"
              title="No favorites yet"
              description="Click the heart icon on tracks you love to add them to your favorites"
            />
          ) : searchQuery ? (
            <NoSearchResults query={searchQuery} />
          ) : (
            <EmptyLibrary
              onScanFolder={handleScanFolder}
              onFolderDrop={handleScanFolder}
              scanning={scanning}
            />
          )}
        </>
      )}

      {/* Edit Metadata Dialog */}
      {editingTrackId && (
        <EditMetadataDialog
          open={editMetadataDialogOpen}
          trackId={editingTrackId}
          onClose={() => {
            setEditMetadataDialogOpen(false);
            setEditingTrackId(null);
          }}
          onSave={(trackId, metadata) => {
            success('Metadata updated successfully');
            // Refresh tracks to show updated metadata
            fetchTracks();
          }}
        />
      )}
    </Container>
    </>
  );
};

export default CozyLibraryView;