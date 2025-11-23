/**
 * CozyLibraryView - Main Library View Orchestrator
 *
 * Refactored from 958 lines to focused orchestrator using extracted components:
 * - useLibraryWithStats hook for data fetching and statistics
 * - LibraryViewRouter for albums/artists navigation
 * - TrackListView for track rendering
 * - LibraryEmptyState for empty states
 * - useLibraryKeyboardShortcuts for keyboard handling
 * - LibrarySearchControls for search/filter UI
 *
 * Responsibilities:
 * - Search/filter orchestration
 * - Batch operations coordination
 * - Layout and header rendering
 * - Component composition
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Container
} from '@mui/material';
import BatchActionsToolbar from './library/BatchActionsToolbar';
import EditMetadataDialog from './library/EditMetadataDialog';
import { useToast } from './shared/Toast';
import { usePlayerAPI } from '../hooks/usePlayerAPI';
import { useTrackSelection } from '../hooks/useTrackSelection';
import { useLibraryWithStats, Track } from '../hooks/useLibraryWithStats';
import { LibraryViewRouter } from './library/LibraryViewRouter';
import { TrackListView } from './library/TrackListView';
import { EmptyState, EmptyLibrary, NoSearchResults } from './shared/EmptyState';
import { LibraryHeader } from './library/LibraryHeader';
import LibrarySearchControls from './CozyLibraryView/LibrarySearchControls';
import { useLibraryKeyboardShortcuts } from './CozyLibraryView/useLibraryKeyboardShortcuts';
import { tokens } from '@/design-system/tokens';

interface CozyLibraryViewProps {
  onTrackPlay?: (track: Track) => void;
  view?: string;
}

const CozyLibraryView: React.FC<CozyLibraryViewProps> = React.memo(({
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
    handleScanFolder,
    // New composition hook provides stats too (optional)
    stats,
    statsLoading
  } = useLibraryWithStats({ view, includeStats: false }); // Disable stats by default for performance

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
  // KEYBOARD SHORTCUTS
  // ============================================================
  useLibraryKeyboardShortcuts({
    filteredTracksCount: filteredTracks.length,
    hasSelection,
    onSelectAll: selectAll,
    onClearSelection: clearSelection,
    onSelectAllInfo: info,
    onClearSelectionInfo: info
  });

  // ============================================================
  // EFFECTS
  // ============================================================

  // Reset navigation state when view changes
  useEffect(() => {
    setSelectedAlbumId(null);
    setSelectedArtistId(null);
    setSelectedArtistName('');
  }, [view]);

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

      <Container maxWidth="xl" sx={{ py: tokens.spacing.xl }}>
        {/* Header */}
        <LibraryHeader view={view} />

        {/* Search and Controls */}
        <LibrarySearchControls
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          onScanFolder={handleScanFolder}
          onRefresh={fetchTracks}
          scanning={scanning}
          loading={loading}
          trackCount={filteredTracks.length}
        />

        {/* Track List or Empty State */}
        {filteredTracks.length === 0 && !loading ? (
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
});

CozyLibraryView.displayName = 'CozyLibraryView';

export default CozyLibraryView;
