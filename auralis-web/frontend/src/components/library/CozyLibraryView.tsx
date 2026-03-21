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

import React, { useState, useMemo, useCallback } from 'react';
import { Box } from '@mui/material';
import BatchActionsToolbar from './Controls/BatchActionsToolbar';
import EditMetadataDialog from './EditMetadataDialog/EditMetadataDialog';
import { SimilarTracksModal } from '../shared/SimilarTracksModal';
import { useTrackSelection } from '@/hooks/library/useTrackSelection';
import { useLibraryWithStats } from '@/hooks/library/useLibraryWithStats';
import type { LibraryTrack } from '@/types/domain';
import type { ViewMode } from '../navigation/ViewToggle';
import { LibraryViewRouter } from './Views/LibraryViewRouter';
import { ViewContainer } from './Views/ViewContainer';
import { TrackListView } from './Views/TrackListView';
import { EmptyState, EmptyLibrary, NoSearchResults } from '../shared/ui/feedback';
import { AlbumCharacterPane } from './AlbumCharacterPane';
import { useLibraryKeyboardShortcuts } from '../CozyLibraryView/useLibraryKeyboardShortcuts';
import { useBatchOperations } from './useBatchOperations';
import { useNavigationState } from './useNavigationState';
import { useMetadataEditing } from './useMetadataEditing';
import { usePlaybackState } from './usePlaybackState';
import { tokens } from '@/design-system';

interface CozyLibraryViewProps {
  onTrackPlay?: (track: LibraryTrack) => void;
  view?: string;
  /** Search query from the top bar */
  searchQuery?: string;
  /** Grid or list view mode */
  viewMode?: ViewMode;
}

const CozyLibraryView = React.memo<CozyLibraryViewProps>(({
  onTrackPlay,
  view = 'songs',
  searchQuery = '',
  viewMode = 'grid',
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

  // Phase 5: Similar tracks modal state
  const [similarTracksModalOpen, setSimilarTracksModalOpen] = useState(false);
  const [similarTrackId, setSimilarTrackId] = useState<number | null>(null);
  const [similarTrackTitle, setSimilarTrackTitle] = useState<string>('');

  const handleFindSimilar = useCallback((trackId: number) => {
    const track = tracks.find(t => t.id === trackId);
    setSimilarTrackId(trackId);
    setSimilarTrackTitle(track?.title || 'this track');
    setSimilarTracksModalOpen(true);
  }, [tracks]);

  const handleCloseSimilarTracksModal = useCallback(() => {
    setSimilarTracksModalOpen(false);
    setSimilarTrackId(null);
    setSimilarTrackTitle('');
  }, []);

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

  // View title and icon based on current view
  const viewConfig = {
    songs: { icon: '🎵', title: 'Songs', subtitle: 'All tracks in your library' },
    favourites: { icon: '❤️', title: 'Favorites', subtitle: 'Your favorite tracks' },
    recent: { icon: '🕐', title: 'Recently Played', subtitle: 'Tracks you played recently' },
    playlists: { icon: '📋', title: 'Playlists', subtitle: 'Your custom playlists' },
  }[view] || { icon: '🎵', title: 'Songs', subtitle: 'All tracks in your library' };

  return (
    <ViewContainer
      icon={viewConfig.icon}
      title={viewConfig.title}
      subtitle={viewConfig.subtitle}
      rightPane={
        <AlbumCharacterPane
          fingerprint={null}
        />
      }
    >
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

      <Box sx={{ py: tokens.spacing.md }}>
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
            onFindSimilar={handleFindSimilar}
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

        {/* Phase 5: Similar Tracks Modal */}
        <SimilarTracksModal
          open={similarTracksModalOpen}
          trackId={similarTrackId}
          trackTitle={similarTrackTitle}
          onClose={handleCloseSimilarTracksModal}
          onTrackPlay={(trackId) => {
            const track = tracks.find(t => t.id === trackId);
            if (track) {
              handlePlayTrack(track);
            }
          }}
          limit={20}
        />
      </Box>
    </ViewContainer>
  );
});

CozyLibraryView.displayName = 'CozyLibraryView';

export default CozyLibraryView;
