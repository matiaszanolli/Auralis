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

import React, { useState, useMemo } from 'react';
import { Container } from '@mui/material';
import BatchActionsToolbar from './Controls/BatchActionsToolbar';
import EditMetadataDialog from './EditMetadataDialog/EditMetadataDialog';
import { useTrackSelection } from '../../hooks/useTrackSelection';
import { useLibraryWithStats, Track } from '../../hooks/useLibraryWithStats';
import type { ViewMode } from '../navigation/ViewToggle';
import { LibraryViewRouter } from './Views/LibraryViewRouter';
import { TrackListView } from './Views/TrackListView';
import { EmptyState, EmptyLibrary, NoSearchResults } from '../shared/ui/feedback';
// TODO: LibraryHeader - component to be created
// import { LibraryHeader } from './library/LibraryHeader';
import LibrarySearchControls from '../CozyLibraryView/LibrarySearchControls';
import { useLibraryKeyboardShortcuts } from '../CozyLibraryView/useLibraryKeyboardShortcuts';
import { useBatchOperations } from './useBatchOperations';
import { useNavigationState } from './useNavigationState';
import { useMetadataEditing } from './useMetadataEditing';
import { usePlaybackState } from './usePlaybackState';
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
  // DATA LAYER
  // ============================================================
  const {
    tracks,
    loading,
    scanning,
    fetchTracks,
    handleScanFolder,
    hasMore,
    totalTracks,
    isLoadingMore,
    loadMore,
  } = useLibraryWithStats({ view, includeStats: false });

  // ============================================================
  // LOCAL UI STATE
  // ============================================================
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');

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
    selectAll,
    clearSelection,
    selectedCount,
    hasSelection,
    isSelected,
    toggleTrack,
  } = useTrackSelection(filteredTracks);

  // Navigation state
  const {
    selectedAlbumId,
    selectedArtistId,
    selectedArtistName,
    handleBackFromAlbum,
    handleBackFromArtist,
    handleAlbumClick,
    handleArtistClick,
  } = useNavigationState({ view });

  // Playback state and handlers
  const {
    currentTrackId,
    isPlaying,
    handlePlayTrack,
    handlePause,
  } = usePlaybackState(onTrackPlay);

  // Metadata editing
  const {
    editMetadataDialogOpen,
    editingTrackId,
    handleCloseEditDialog,
    handleSaveMetadata,
    handleEditMetadata,
  } = useMetadataEditing(fetchTracks);

  // Batch operations
  const {
    handleBulkAddToQueue,
    handleBulkAddToPlaylist,
    handleBulkRemove,
    handleBulkToggleFavorite,
  } = useBatchOperations({
    selectedTracks,
    selectedCount,
    view,
    onFetchTracks: fetchTracks,
    onClearSelection: clearSelection,
  });

  // Keyboard shortcuts
  useLibraryKeyboardShortcuts({
    filteredTracksCount: filteredTracks.length,
    hasSelection,
    onSelectAll: selectAll,
    onClearSelection: clearSelection,
    onSelectAllInfo: () => {},
    onClearSelectionInfo: () => {}
  });

  // ============================================================
  // RENDER - View Routing
  // ============================================================

  // Render routed view for albums/artists or when navigating album/artist details
  if (view === 'albums' || view === 'artists' || selectedAlbumId !== null || selectedArtistId !== null) {
    return (
      <LibraryViewRouter
        view={view}
        selectedAlbumId={selectedAlbumId}
        selectedArtistId={selectedArtistId}
        selectedArtistName={selectedArtistName}
        currentTrackId={currentTrackId}
        isPlaying={isPlaying}
        onBackFromAlbum={handleBackFromAlbum}
        onBackFromArtist={handleBackFromArtist}
        onAlbumClick={handleAlbumClick}
        onArtistClick={handleArtistClick}
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
        {/* Header - LibraryHeader component to be created */}
        {/* <LibraryHeader view={view} /> */}

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
            onPause={handlePause}
            onEditMetadata={handleEditMetadata}
            onLoadMore={loadMore}
          />
        )}

        {/* Edit Metadata Dialog */}
        {editingTrackId && (
          <EditMetadataDialog
            open={editMetadataDialogOpen}
            trackId={editingTrackId}
            onClose={handleCloseEditDialog}
            onSave={handleSaveMetadata}
          />
        )}
      </Container>
    </>
  );
});

CozyLibraryView.displayName = 'CozyLibraryView';

export default CozyLibraryView;
