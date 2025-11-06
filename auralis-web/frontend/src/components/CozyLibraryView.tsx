/**
 * CozyLibraryView - Main Library View Orchestrator
 *
 * Refactored from 958 lines to focused orchestrator using extracted components:
 * - useLibraryData hook for data fetching
 * - LibraryViewRouter for albums/artists navigation
 * - TrackListView for track rendering
 * - LibraryEmptyState for empty states
 *
 * Responsibilities:
 * - Search/filter orchestration
 * - Batch operations coordination
 * - Keyboard shortcuts
 * - Layout and header rendering
 * - Component composition
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Container,
  IconButton,
  Paper,
  Tooltip,
  Typography
} from '@mui/material';
import {
  FolderOpen,
  Refresh
} from '@mui/icons-material';
import SearchBar from './navigation/SearchBar';
import ViewToggle, { ViewMode } from './navigation/ViewToggle';
import BatchActionsToolbar from './library/BatchActionsToolbar';
import EditMetadataDialog from './library/EditMetadataDialog';
import { useToast } from './shared/Toast';
import { usePlayerAPI } from '../hooks/usePlayerAPI';
import { useTrackSelection } from '../hooks/useTrackSelection';
import { useLibraryData, Track } from '../hooks/useLibraryData';
import { LibraryViewRouter } from './library/LibraryViewRouter';
import { TrackListView } from './library/TrackListView';
import { LibraryEmptyState } from './library/LibraryEmptyState';

interface CozyLibraryViewProps {
  onTrackPlay?: (track: Track) => void;
  view?: string;
}

const CozyLibraryView: React.FC<CozyLibraryViewProps> = ({
  onTrackPlay,
  view = 'songs'
}) => {
  // ============================================================
  // DATA LAYER - Extracted to useLibraryData hook
  // ============================================================
  const {
    tracks,
    loading,
    hasMore,
    totalTracks,
    isLoadingMore,
    scanning,
    fetchTracks,
    loadMore,
    handleScanFolder
  } = useLibraryData({ view });

  // ============================================================
  // LOCAL UI STATE
  // ============================================================
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [currentTrackId, setCurrentTrackId] = useState<number | undefined>(undefined);
  const [isPlaying, setIsPlaying] = useState(false);

  // Navigation state
  const [selectedAlbumId, setSelectedAlbumId] = useState<number | null>(null);
  const [selectedArtistId, setSelectedArtistId] = useState<number | null>(null);
  const [selectedArtistName, setSelectedArtistName] = useState<string>('');

  // Metadata editing
  const [editMetadataDialogOpen, setEditMetadataDialogOpen] = useState(false);
  const [editingTrackId, setEditingTrackId] = useState<number | null>(null);

  const { success, error, info } = useToast();

  // Real player API for playback
  const { playTrack } = usePlayerAPI();

  // Filtered tracks (search)
  const filteredTracks = useMemo(() => {
    if (!searchQuery.trim()) {
      return tracks;
    }
    return tracks.filter(track =>
      track.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      track.artist.toLowerCase().includes(searchQuery.toLowerCase()) ||
      track.album.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [searchQuery, tracks]);

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

  // ============================================================
  // EFFECTS
  // ============================================================

  // Reset navigation state when view changes
  useEffect(() => {
    setSelectedAlbumId(null);
    setSelectedArtistId(null);
    setSelectedArtistName('');
  }, [view]);

  // Keyboard shortcuts (Ctrl+A, Escape)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
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

      // Escape: Clear selection
      if (event.key === 'Escape' && hasSelection) {
        event.preventDefault();
        clearSelection();
        info('Selection cleared');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [filteredTracks, hasSelection, selectAll, clearSelection, info]);

  // ============================================================
  // HANDLERS
  // ============================================================

  // Track playback
  const handlePlayTrack = async (track: Track) => {
    await playTrack(track);
    setCurrentTrackId(track.id);
    setIsPlaying(true);
    success(`Now playing: ${track.title}`);
    onTrackPlay?.(track);
  };

  // Metadata editing
  const handleEditMetadata = (trackId: number) => {
    setEditingTrackId(trackId);
    setEditMetadataDialogOpen(true);
  };

  // Batch operations
  const handleBulkAddToQueue = async () => {
    try {
      const selectedTrackIds = Array.from(selectedTracks);
      for (const trackId of selectedTrackIds) {
        await fetch('/api/player/queue/add-track', {
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
    info('Bulk add to playlist - Coming soon!');
  };

  const handleBulkRemove = async () => {
    if (!confirm(`Remove ${selectedCount} tracks?`)) {
      return;
    }

    try {
      if (view === 'favourites') {
        for (const trackId of selectedTracks) {
          await fetch(`/api/library/tracks/${trackId}/favorite`, {
            method: 'DELETE'
          });
        }
        success(`Removed ${selectedCount} tracks from favorites`);
      } else {
        info('Bulk delete from library requires API implementation');
      }

      clearSelection();
      await fetchTracks();
    } catch (err) {
      error('Failed to remove tracks');
    }
  };

  const handleBulkToggleFavorite = async () => {
    try {
      for (const trackId of selectedTracks) {
        await fetch(`/api/library/tracks/${trackId}/favorite`, {
          method: 'POST'
        });
      }
      success(`Toggled favorite for ${selectedCount} tracks`);
      clearSelection();
      await fetchTracks();
    } catch (err) {
      error('Failed to toggle favorites');
    }
  };

  // ============================================================
  // RENDER - View Routing
  // ============================================================

  // Check if we should render a routed view (albums/artists)
  // Only render router for albums/artists views or when navigating album/artist details
  if (view === 'albums' || view === 'artists' || selectedAlbumId !== null || selectedArtistId !== null) {
    return (
      <LibraryViewRouter
        view={view}
        selectedAlbumId={selectedAlbumId}
        selectedArtistId={selectedArtistId}
        selectedArtistName={selectedArtistName}
        currentTrackId={currentTrackId}
        isPlaying={isPlaying}
        onBackFromAlbum={() => {
          setSelectedAlbumId(null);
          // If we came from artist view, stay in artist detail
          // (selectedArtistId will still be set)
        }}
        onBackFromArtist={() => {
          setSelectedArtistId(null);
          setSelectedArtistName('');
        }}
        onAlbumClick={setSelectedAlbumId}
        onArtistClick={(id, name) => {
          setSelectedArtistId(id);
          setSelectedArtistName(name);
        }}
        onTrackPlay={handlePlayTrack}
      />
    );
  }

  // ============================================================
  // RENDER - Main Track List View
  // ============================================================

  return (
    <>
      {/* Batch Actions Toolbar */}
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
                  onClick={() => fetchTracks()}
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

        {/* Track List or Empty State */}
        {filteredTracks.length === 0 && !loading ? (
          <LibraryEmptyState
            view={view}
            searchQuery={searchQuery}
            scanning={scanning}
            onScanFolder={handleScanFolder}
          />
        ) : (
          <TrackListView
            tracks={filteredTracks}
            viewMode={viewMode}
            loading={loading}
            hasMore={hasMore}
            totalTracks={totalTracks}
            isLoadingMore={isLoadingMore}
            currentTrackId={currentTrackId}
            isPlaying={isPlaying}
            selectedTracks={selectedTracks}
            isSelected={isSelected}
            onToggleSelect={toggleTrack}
            onTrackPlay={handlePlayTrack}
            onPause={() => setIsPlaying(false)}
            onEditMetadata={handleEditMetadata}
            onLoadMore={loadMore}
          />
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
            onSave={async () => {
              success('Metadata updated successfully');
              await fetchTracks();
            }}
          />
        )}
      </Container>
    </>
  );
};

export default CozyLibraryView;
