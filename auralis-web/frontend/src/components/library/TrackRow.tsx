import React, { useState } from 'react';
import { PlayArrow, Pause, MoreVert, MusicNote } from '@mui/icons-material';
import { ContextMenu, getTrackContextActions } from '../shared/ContextMenu';
import { useToast } from '../shared/Toast';
import * as playlistService from '../../services/playlistService';
import {
  RowContainer,
  ActiveIndicator,
  TrackNumberBox,
  TrackNumber,
  PlayButton,
  AlbumArtThumbnail,
  TrackInfo,
  TrackTitle,
  TrackArtist,
  TrackAlbum,
  TrackDuration,
  MoreButton,
} from './TrackRow.styles';

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
  onPlay: (trackId: number) => void;
  onPause?: () => void;
  onDoubleClick?: (trackId: number) => void;
  onEditMetadata?: (trackId: number) => void;
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
  onPlay,
  onPause,
  onDoubleClick,
  onEditMetadata,
  onToggleFavorite,
  onShowAlbum,
  onShowArtist,
  onShowInfo,
  onDelete,
}) => {
  const [imageError, setImageError] = useState(false);
  const [contextMenuPosition, setContextMenuPosition] = useState<{top: number, left: number} | null>(null);
  const [playlists, setPlaylists] = useState<playlistService.Playlist[]>([]);
  const [isLoadingPlaylists, setIsLoadingPlaylists] = useState(false);
  const { success, info, error } = useToast();

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const fetchPlaylists = async () => {
    setIsLoadingPlaylists(true);
    try {
      const response = await playlistService.getPlaylists();
      setPlaylists(response.playlists);
    } catch (err) {
      console.error('Failed to load playlists:', err);
    } finally {
      setIsLoadingPlaylists(false);
    }
  };

  const handleAddToPlaylist = async (playlistId: number, playlistName: string) => {
    try {
      await playlistService.addTracksToPlaylist(playlistId, [track.id]);
      success(`Added to "${playlistName}"`);
    } catch (err) {
      error(`Failed to add to playlist: ${err}`);
    }
  };

  const handleCreatePlaylist = async (playlist: playlistService.Playlist) => {
    try {
      await playlistService.addTracksToPlaylist(playlist.id, [track.id]);
      success(`Added to "${playlist.name}"`);
    } catch (err) {
      error(`Failed to add to playlist: ${err}`);
    }
  };

  const handlePlayClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isCurrent && isPlaying && onPause) {
      onPause();
    } else {
      onPlay(track.id);
    }
  };

  const handleRowClick = () => {
    onPlay(track.id);
  };

  const handleRowDoubleClick = () => {
    onDoubleClick?.(track.id);
  };

  const handleMoreClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setContextMenuPosition({ top: e.clientY, left: e.clientX });
  };

  const handleTrackContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenuPosition({ top: e.clientY, left: e.clientX });
  };

  const handleCloseContextMenu = () => {
    setContextMenuPosition(null);
  };

  const isCurrentStr = isCurrent ? 'true' : 'false';

  return (
    <>
      <RowContainer
        iscurrent={isCurrentStr}
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
          <PlayButton
            className="play-button"
            onClick={handlePlayClick}
            size="small"
          >
            {isCurrent && isPlaying ? <Pause /> : <PlayArrow />}
          </PlayButton>
        </TrackNumberBox>

        {/* Album Art Thumbnail */}
        {track.albumArt && !imageError ? (
          <AlbumArtThumbnail>
            <img
              src={track.albumArt}
              alt={track.album || track.title}
              onError={() => setImageError(true)}
            />
          </AlbumArtThumbnail>
        ) : (
          <AlbumArtThumbnail>
            <MusicNote sx={{ color: 'rgba(255, 255, 255, 0.3)', fontSize: '20px' }} />
          </AlbumArtThumbnail>
        )}

        {/* Track Title & Artist */}
        <TrackInfo>
          <TrackTitle iscurrent={isCurrentStr}>
            {track.title}
          </TrackTitle>
          <TrackArtist>
            {track.artist}
          </TrackArtist>
        </TrackInfo>

        {/* Album Name (hidden on mobile) */}
        {track.album && (
          <TrackAlbum sx={{ display: { xs: 'none', md: 'block' } }}>
            {track.album}
          </TrackAlbum>
        )}

        {/* Duration */}
        <TrackDuration>
          {formatDuration(track.duration)}
        </TrackDuration>

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
        actions={getTrackContextActions(
          track.id,
          track.favorite || false,
          {
            onPlay: () => {
              onPlay(track.id);
              info(`Now playing: ${track.title}`);
            },
            onAddToQueue: () => {
              success(`Added "${track.title}" to queue`);
              // TODO: Implement actual queue functionality
            },
            onAddToPlaylist: handleCloseContextMenu,
            onToggleLove: onToggleFavorite ? () => {
              onToggleFavorite(track.id);
              success(track.favorite ? `Removed "${track.title}" from favorites` : `Added "${track.title}" to favorites`);
            } : undefined,
            onShowAlbum: onShowAlbum && track.album_id ? () => {
              onShowAlbum(track.album_id!);
            } : undefined,
            onShowArtist: onShowArtist ? () => {
              onShowArtist(track.artist);
            } : undefined,
            onShowInfo: onShowInfo ? () => {
              onShowInfo(track.id);
            } : undefined,
            onEditMetadata: onEditMetadata ? () => {
              onEditMetadata(track.id);
            } : undefined,
            onDelete: onDelete ? () => {
              onDelete(track.id);
            } : undefined,
          }
        )}
        // Playlist support
        trackId={track.id}
        trackTitle={track.title}
        playlists={playlists}
        isLoadingPlaylists={isLoadingPlaylists}
        onPlaylistsLoad={fetchPlaylists}
        onAddToPlaylist={handleAddToPlaylist}
        onCreatePlaylist={handleCreatePlaylist}
      />
    </>
  );
};

export default TrackRow;
