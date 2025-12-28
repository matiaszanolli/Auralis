import React from 'react';
import { MoreVert } from '@mui/icons-material';
import { ContextMenu } from '../../../shared/ContextMenu';
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
import { useTrackFormatting } from './useTrackFormatting';

export interface Track {
  id: number;
  title: string;
  artist: string;
  album?: string;
  album_id?: number;
  duration: number;
  albumArt?: string;
  favorite?: boolean;
}

interface TrackRowProps {
  track: Track;
  index: number;
  isPlaying?: boolean;
  isCurrent?: boolean;
  isAnyPlaying?: boolean; // Phase 1: Global playback state for dimming non-current rows
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

export const TrackRow: React.FC<TrackRowProps> = ({
  track,
  index,
  isPlaying = false,
  isCurrent = false,
  isAnyPlaying = false, // Phase 1: Default to false (no global playback)
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
}) => {
  // Image state management
  const { imageError, handleImageError, shouldShowImage } = useTrackImage();

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

  return (
    <>
      <RowContainer
        iscurrent={isCurrentStr}
        isanyplaying={isAnyPlayingStr}
        onClick={handleRowClick}
        onDoubleClick={handleRowDoubleClick}
        onContextMenu={handleTrackContextMenu}
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
          />
        </TrackNumberBox>

        {/* Album Art Thumbnail */}
        <TrackRowAlbumArt
          albumArt={track.albumArt}
          title={track.title}
          album={track.album}
          shouldShowImage={shouldShowImage(track.albumArt)}
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

export default TrackRow;
