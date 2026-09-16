import { KeyboardEvent, memo } from 'react';
import MoreVert from '@mui/icons-material/MoreVert';
import { ContextMenu } from '@/components/shared/ContextMenu';
import {
  RowContainer,
  ActiveIndicator,
  TrackNumberBox,
  TrackNumber,
  MoreButton,
} from './TrackRow.styles';
import TrackRowPlayButton from './TrackRowPlayButton';
import TrackRowAlbumArt from './TrackRowAlbumArt';
import TrackRowMetadata from './TrackRowMetadata';
import { useTrackRowHandlers } from './useTrackRowHandlers';
import { useTrackContextMenu } from './useTrackContextMenu';
import { useTrackImage } from './useTrackImage';
import { withArtworkSize } from '@/services/artworkService';
import { useTrackFormatting } from './useTrackFormatting';
import type { LibraryTrack } from '@/types/domain';

interface TrackRowProps {
  track: LibraryTrack;
  index: number;
  isPlaying?: boolean;
  isCurrent?: boolean;
  isAnyPlaying?: boolean; // Phase 1: Global playback state for dimming non-current rows
  /** Batch-selection state (#5011) — reflected as aria-selected, distinct
   *  from roving-tabindex focus below. */
  isSelected?: boolean;
  /** Roving-tabindex focus stop (#5011): exactly one row in the listbox is
   *  tabIndex=0 at a time; the rest are -1 so Tab enters/exits the list in
   *  one stop while ArrowUp/ArrowDown/Home/End move focus between options,
   *  per the WAI-ARIA APG listbox pattern. Defaults to 0 for callers (e.g.
   *  existing tests) that don't manage roving focus. */
  tabIndex?: number;
  onPlay: (trackId: number) => void;
  onPause?: () => void;
  onDoubleClick?: (trackId: number) => void;
  onEditMetadata?: (trackId: number) => void;
  onFindSimilar?: (trackId: number) => void; // Phase 5: Find similar tracks
  onToggleFavorite?: (trackId: number) => void;
  onShowAlbum?: (albumId: number) => void;
  onShowArtist?: (artistName: string) => void;
  onShowInfo?: (trackId: number) => void;
  onDelete?: (trackId: number) => void;
}

const TrackRowComponent = ({
  track,
  index,
  isPlaying = false,
  isCurrent = false,
  isAnyPlaying = false, // Phase 1: Default to false (no global playback)
  isSelected = false,
  tabIndex = 0,
  onPlay,
  onPause,
  onDoubleClick,
  onEditMetadata,
  onFindSimilar,
  onToggleFavorite,
  onShowAlbum,
  onShowArtist,
  onShowInfo,
  onDelete,
}: TrackRowProps) => {
  // Image state management
  const { imageError: _imageError, handleImageError, shouldShowImage } = useTrackImage();

  // Play/pause and row click handlers
  const { handlePlayClick, handleRowClick, handleRowDoubleClick } =
    useTrackRowHandlers({
      trackId: track.id,
      isCurrent,
      isPlaying,
      onPlay,
      onPause,
      onDoubleClick,
    });

  // Duration formatting utility
  const { formatDuration } = useTrackFormatting();

  // Context menu and playlist operations
  const {
    contextMenuPosition,
    playlists,
    isLoadingPlaylists,
    handleMoreClick,
    handleTrackContextMenu,
    handleCloseContextMenu,
    handleAddToPlaylist,
    handleCreatePlaylist,
    contextActions,
  } = useTrackContextMenu({
    track,
    onPlay,
    onEditMetadata,
    onFindSimilar,
    onToggleFavorite,
    onShowAlbum,
    onShowArtist,
    onShowInfo,
    onDelete,
  });

  const isCurrentStr = isCurrent ? 'true' : 'false';
  const isAnyPlayingStr = isAnyPlaying ? 'true' : 'false'; // Phase 1: Convert to string for styled-components

  // The row thumbnail is 40×40; request an ~80px (retina) variant so the browser
  // doesn't decode/hold the full-resolution album bitmap per row (#4447).
  const rowArtworkUrl = withArtworkSize(track.artworkUrl ?? undefined, 80);

  return (
    <>
      <RowContainer
        tabIndex={tabIndex}
        role="option"
        aria-label={`${track.title} by ${track.artist}`}
        aria-selected={isSelected}
        data-track-index={index}
        iscurrent={isCurrentStr}
        isanyplaying={isAnyPlayingStr}
        onClick={handleRowClick}
        onDoubleClick={handleRowDoubleClick}
        onContextMenu={handleTrackContextMenu}
        onKeyDown={(e: KeyboardEvent) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            handleRowClick();
          } else if (e.key === ' ') {
            e.preventDefault();
            handleRowClick();
          }
        }}
      >
        {isCurrent && <ActiveIndicator />}

        {/* Track Number / Play Button */}
        <TrackNumberBox>
          <TrackNumber className="track-number" iscurrent={isCurrentStr}>
            {index + 1}
          </TrackNumber>
          <TrackRowPlayButton
            isCurrent={isCurrent}
            isPlaying={isPlaying}
            onClick={handlePlayClick}
            trackTitle={track.title}
          />
        </TrackNumberBox>

        {/* Album Art Thumbnail */}
        <TrackRowAlbumArt
          albumArt={rowArtworkUrl}
          title={track.title}
          album={track.album}
          shouldShowImage={shouldShowImage(rowArtworkUrl)}
          onImageError={handleImageError}
        />

        {/* Track Metadata - Title, Artist, Album, Duration */}
        <TrackRowMetadata
          title={track.title}
          artist={track.artist}
          album={track.album}
          duration={formatDuration(track.duration)}
          isCurrent={isCurrent}
        />

        {/* More Button */}
        <MoreButton
          className="more-button"
          onClick={handleMoreClick}
          size="small"
          aria-label={`More options for ${track.title}`}
        >
          <MoreVert />
        </MoreButton>
      </RowContainer>

      {/* Unified Track Context Menu */}
      <ContextMenu
        open={Boolean(contextMenuPosition)}
        anchorPosition={contextMenuPosition || undefined}
        onClose={handleCloseContextMenu}
        actions={contextActions}
        // Playlist support
        trackId={track.id}
        trackTitle={track.title}
        playlists={playlists}
        isLoadingPlaylists={isLoadingPlaylists}
        onPlaylistsLoad={() => {
          /* fetch playlists */
        }}
        onAddToPlaylist={handleAddToPlaylist}
        onCreatePlaylist={handleCreatePlaylist}
      />
    </>
  );
};

/**
 * Memoized TrackRow component.
 * Uses default shallow comparison so all props — including the 10 callback props
 * (onPlay, onPause, onDoubleClick, onEditMetadata, onFindSimilar, etc.) — are checked.
 * Parents must wrap callbacks in useCallback to avoid unnecessary re-renders.
 * The previous custom comparator silently dropped callback prop changes,
 * causing stale closure bugs (#2540).
 */
export const TrackRow = memo<TrackRowProps>(TrackRowComponent);

export default TrackRow;
