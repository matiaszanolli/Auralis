/**
 * CozyLibraryView - Main Library View Orchestrator
 *
 * Refactored from 958 lines to focused orchestrator using extracted components:
 * - useLibraryWithStats hook for data fetching and statistics
 * - LibraryViewRouter for albums/artists navigation
 * - TrackListView for track rendering
 * - LibraryEmptyContent for empty states
 * - useLibraryKeyboardShortcuts for keyboard handling
 * - BatchActionsToolbar for multi-select actions
 *
 * The search query arrives from the top bar as a prop; this view has no
 * search UI of its own.
 *
 * Responsibilities:
 * - Search/filter orchestration
 * - Batch operations coordination
 * - Layout and header rendering
 * - Component composition
 */

import { memo, useMemo, useState, useEffect, lazy, Suspense } from 'react';
import { Box } from '@mui/material';
import BatchActionsToolbar from './Controls/BatchActionsToolbar';
// Lazy-load the on-demand dialogs so their (~760 LOC + transitive deps) bundle
// stays out of the initial CozyLibraryView chunk (#3956).
const EditMetadataDialog = lazy(() => import('./EditMetadataDialog/EditMetadataDialog'));
const SimilarTracksModal = lazy(() => import('@/components/shared/SimilarTracksModal').then((m) => ({ default: m.SimilarTracksModal })));
import { useTrackSelection } from '@/hooks/library/useTrackSelection';
import { useLibraryWithStats } from '@/hooks/library/useLibraryWithStats';
import type { ViewMode } from '@/components/navigation/ViewToggle';
import { LibraryViewRouter } from './Views/LibraryViewRouter';
import { ViewContainer } from './Views/ViewContainer';
import { TrackListView } from './Views/TrackListView';
import { LibraryEmptyContent } from '@/components/CozyLibraryView/LibraryEmptyContent';
import { AlbumCharacterPane } from './AlbumCharacterPane';
import { useLibraryKeyboardShortcuts } from '@/components/CozyLibraryView/useLibraryKeyboardShortcuts';
import { useBatchOperations } from './useBatchOperations';
import { useNavigationState, parsePlaylistViewId } from './useNavigationState';
import { useMetadataEditing } from './useMetadataEditing';
import { usePlaybackState } from './usePlaybackState';
import { useSimilarTracksModal } from './useSimilarTracksModal';
import { SearchResultsAnnouncement } from './SearchResultsAnnouncement';
import { tokens } from '@/design-system';

interface CozyLibraryViewProps {
  view?: string;
  /** Search query from the top bar */
  searchQuery?: string;
  /** Grid or list view mode */
  viewMode?: ViewMode;
  /** Navigate to another view id; PlaylistDetailView's Back uses it (#6007). */
  onNavigate?: (view: string) => void;
}

// View title and icon based on current view — static, so it lives at module
// scope instead of being rebuilt (with new identities) every render.
// 'recent' and 'playlists' are deliberately absent (#5620): neither had a
// data path, so both rendered the entire unfiltered library under a false
// heading. Unknown views (e.g. a stale persisted 'recent') fall back to the
// honest Songs config below.
const VIEW_CONFIG: Record<string, { icon: string; title: string; subtitle: string }> = {
  songs: { icon: '🎵', title: 'Songs', subtitle: 'All tracks in your library' },
  favourites: { icon: '❤️', title: 'Favorites', subtitle: 'Your favorite tracks' },
};

const CozyLibraryView = memo<CozyLibraryViewProps>(({
  view = 'songs',
  searchQuery = '',
  viewMode = 'grid',
  onNavigate,
}) => {
  // Sidebar playlist clicks set `playlist-<id>` view ids (#6007).
  const playlistId = parsePlaylistViewId(view);

  // #5866: debounce the top-bar query before it hits the backend, so typing
  // does not fire a request per keystroke. The client-side filter below still
  // runs on the un-debounced value for instant feedback over loaded pages.
  const [debouncedSearch, setDebouncedSearch] = useState(searchQuery);
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchQuery), 250);
    return () => clearTimeout(t);
  }, [searchQuery]);

  // ── DATA LAYER ──
  const {
    tracks,
    loading,
    error,
    scanning,
    refreshTracks,
    handleScanFolder,
    hasMore,
    totalTracks,
    isLoadingMore,
    loadMore,
  } = useLibraryWithStats({
    view,
    search: debouncedSearch,
    includeStats: false,
    autoLoad: playlistId === null,
  });

  // Filtered tracks (search)
  const filteredTracks = useMemo(() => {
    if (!searchQuery.trim()) {
      return tracks;
    }
    return tracks.filter(track =>
      track.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      track.artist.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (track.album ?? '').toLowerCase().includes(searchQuery.toLowerCase())
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
    handlePlayPause,
  } = usePlaybackState();

  // Metadata editing
  const {
    editMetadataDialogOpen,
    editingTrackId,
    editSession,
    handleCloseEditDialog,
    handleSaveMetadata,
    handleEditMetadata,
  // #5626: post-mutation refreshes happen in place — the list keeps
  // scroll, focus, selection and loaded pages.
  } = useMetadataEditing(refreshTracks);

  // Phase 5: Similar tracks modal state
  const {
    similarTracksModalOpen,
    similarTrackId,
    similarTrackTitle,
    handleFindSimilar,
    handleCloseSimilarTracksModal,
    handlePlaySimilarTrack,
  } = useSimilarTracksModal({ tracks, onPlayTrack: handlePlayTrack });

  // Batch operations
  const {
    handleBulkAddToQueue,
    handleBulkAddToPlaylist,
    handleBulkRemove,
    handleBulkToggleFavorite,
    isSubmitting: isBatchSubmitting,
  } = useBatchOperations({
    selectedTracks,
    selectedCount,
    onFetchTracks: refreshTracks,
    onClearSelection: clearSelection,
    // #5118: bulk favorite needs each track's current state to pick POST vs
    // DELETE — the backend has no toggle endpoint.
    tracks,
  });

  // The track list is on screen only for songs/favourites; albums, artists,
  // playlists and the detail views route elsewhere.
  const showsTrackList = playlistId === null && view !== 'albums' && view !== 'artists'
    && selectedAlbumId === null && selectedArtistId === null;

  // One mounted instance serves every view, so a selection made in one would
  // otherwise survive into another where bulk actions hit tracks the user can no
  // longer see (#6010). (useTrackSelection also drops ids a search filtered out.)
  useEffect(() => {
    clearSelection();
  }, [view, playlistId, clearSelection]);

  // Keyboard shortcuts: Ctrl+A must not silently select the hidden track list.
  useLibraryKeyboardShortcuts({
    filteredTracksCount: showsTrackList ? filteredTracks.length : 0,
    hasSelection,
    onSelectAll: selectAll,
    onClearSelection: clearSelection,
  });

  // ── RENDER - View Routing ──

  // Playlist details arrive as `playlist-<id>` view ids (#6007) and must
  // route before the track-list fall-through, which used to paginate the
  // entire library under a "Songs" heading for them.
  if (!showsTrackList) {
    return (
      <LibraryViewRouter
        view={view}
        searchQuery={debouncedSearch}
        playlistId={playlistId}
        onBackToSongs={onNavigate ? () => onNavigate('songs') : undefined}
        selectedAlbumId={selectedAlbumId}
        selectedArtistId={selectedArtistId}
        selectedArtistName={selectedArtistName}
        onBackFromAlbum={handleBackFromAlbum}
        onBackFromArtist={handleBackFromArtist}
        onAlbumClick={handleAlbumClick}
        onArtistClick={handleArtistClick}
      />
    );
  }

  // ── RENDER - Main Track List View ──

  // View title and icon based on current view
  const viewConfig = VIEW_CONFIG[view] ?? VIEW_CONFIG.songs;

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
          // #4240: library (non-favourites) track removal has no backend
          // deletion route yet — hide the button rather than wire it to a
          // silent no-op toast.
          onRemove={view === 'favourites' ? handleBulkRemove : undefined}
          onToggleFavorite={handleBulkToggleFavorite}
          onClearSelection={clearSelection}
          context={view === 'favourites' ? 'favorites' : 'library'}
          disabled={isBatchSubmitting}
        />
      )}

      <Box sx={{ py: tokens.spacing.md }}>
        {/* Search result counts, "no results" and loading, for screen readers
            (#5668). Always mounted so the region exists before it changes. */}
        <SearchResultsAnnouncement resultCount={filteredTracks.length} query={searchQuery} loading={loading} />

        {/* Track List or Empty State */}
        {filteredTracks.length === 0 && !loading ? (
          <LibraryEmptyContent
            view={view}
            searchQuery={searchQuery}
            scanning={scanning}
            onScanFolder={handleScanFolder}
            error={tracks.length === 0 ? error : null}
            onRetry={refreshTracks}
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
            onPause={handlePlayPause}
            onEditMetadata={handleEditMetadata}
            onFindSimilar={handleFindSimilar}
            onLoadMore={loadMore}
          />
        )}

        {/* Edit Metadata Dialog — lazy-loaded (#3956). Mounted from the first
            open on and hidden via `open`, so the exit transition plays (#5397). */}
        {editingTrackId !== null && (
          <Suspense fallback={null}>
            <EditMetadataDialog
              key={editSession}
              open={editMetadataDialogOpen}
              trackId={editingTrackId}
              onClose={handleCloseEditDialog}
              onSave={handleSaveMetadata}
            />
          </Suspense>
        )}

        {/* Similar Tracks Modal — lazy-loaded, not mounted before its first open
            (#3956); stays mounted after close so the exit transition plays (#5397). */}
        {similarTrackId !== null && (
          <Suspense fallback={null}>
            <SimilarTracksModal
              open={similarTracksModalOpen}
              trackId={similarTrackId}
              trackTitle={similarTrackTitle}
              onClose={handleCloseSimilarTracksModal}
              onTrackPlay={handlePlaySimilarTrack}
              limit={20}
            />
          </Suspense>
        )}
      </Box>
    </ViewContainer>
  );
});

CozyLibraryView.displayName = 'CozyLibraryView';

export default CozyLibraryView;
