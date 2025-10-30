import React, { useState } from 'react';
import { Box, Typography, IconButton, styled } from '@mui/material';
import { PlayArrow, Pause, MoreVert, MusicNote } from '@mui/icons-material';
import { colors, gradients, spacing, borderRadius, transitions } from '../../theme/auralisTheme';
import { TrackContextMenu } from '../shared/TrackContextMenu';
import { useToast } from '../shared/Toast';

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

const RowContainer = styled(Box)<{ iscurrent?: string }>(({ iscurrent }) => ({
  display: 'flex',
  alignItems: 'center',
  height: '48px',
  padding: `0 ${spacing.md}px`,
  borderRadius: `${borderRadius.xs}px`,
  cursor: 'pointer',
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)', // Smooth easing
  background: iscurrent === 'true' ? 'rgba(102, 126, 234, 0.12)' : 'transparent',
  border: iscurrent === 'true' ? '1px solid rgba(102, 126, 234, 0.2)' : '1px solid transparent',
  position: 'relative',
  marginBottom: `${spacing.xs / 2}px`,
  boxShadow: iscurrent === 'true' ? '0 0 0 1px rgba(102, 126, 234, 0.1)' : 'none',

  '&:hover': {
    background: iscurrent === 'true'
      ? 'rgba(102, 126, 234, 0.18)'
      : 'rgba(102, 126, 234, 0.08)',
    transform: 'translateX(4px) scale(1.005)', // Subtle scale for depth
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',

    '& .track-number': {
      opacity: 0,
      transform: 'scale(0.8)',
    },

    '& .play-button': {
      opacity: 1,
      transform: 'scale(1)',
    },

    '& .more-button': {
      opacity: 1,
    },

    '& .track-title': {
      color: '#667eea',
    },

    '& .album-art': {
      transform: 'scale(1.05)',
      boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
    },
  },

  '&:active': {
    transform: 'translateX(2px) scale(0.995)',
  },
}));

const ActiveIndicator = styled(Box)({
  position: 'absolute',
  left: 0,
  top: 0,
  bottom: 0,
  width: '3px',
  background: gradients.aurora,
  borderRadius: `0 ${spacing.xs / 2}px ${spacing.xs / 2}px 0`,
});

const TrackNumberBox = styled(Box)({
  minWidth: '40px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  position: 'relative',
});

const TrackNumber = styled(Typography)<{ iscurrent?: string }>(({ iscurrent }) => ({
  fontSize: '14px',
  fontWeight: 500,
  color: iscurrent === 'true' ? '#667eea' : colors.text.secondary,
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
}));

const PlayButton = styled(IconButton)({
  position: 'absolute',
  width: '32px',
  height: '32px',
  opacity: 0,
  transform: 'scale(0.8)',
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
  color: '#667eea',

  '&:hover': {
    background: 'rgba(102, 126, 234, 0.15)',
    transform: 'scale(1.1)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
});

const AlbumArtThumbnail = styled(Box)({
  width: '40px',
  height: '40px',
  marginRight: `${spacing.md / 1.33}px`, // 12px
  borderRadius: `${borderRadius.xs}px`,
  overflow: 'hidden',
  flexShrink: 0,
  background: gradients.aurora,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',

  '& img': {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  },
});

const TrackInfo = styled(Box)({
  flex: 1,
  minWidth: 0,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
});

const TrackTitle = styled(Typography)<{ iscurrent?: string }>(({ iscurrent }) => ({
  fontSize: '14px',
  fontWeight: iscurrent === 'true' ? 600 : 500,
  color: colors.text.primary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: 1.4,
  transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
}));

const TrackArtist = styled(Typography)({
  fontSize: '13px',
  fontWeight: 400,
  color: colors.text.secondary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: 1.4,
});

const TrackAlbum = styled(Typography)({
  fontSize: '13px',
  fontWeight: 400,
  color: colors.text.secondary,
  minWidth: '200px',
  maxWidth: '300px',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  marginRight: `${spacing.md}px`,
  display: { xs: 'none', md: 'block' },
});

const TrackDuration = styled(Typography)({
  fontSize: '13px',
  fontWeight: 400,
  color: colors.text.disabled,
  minWidth: '50px',
  textAlign: 'right',
  marginRight: `${spacing.sm}px`,
});

const MoreButton = styled(IconButton)({
  width: '32px',
  height: '32px',
  opacity: 0,
  transition: `opacity ${transitions.fast}`,
  color: colors.text.secondary,

  '&:hover': {
    background: 'rgba(102, 126, 234, 0.12)',
    color: '#667eea',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
});

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
  const { success, info } = useToast();

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
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

      {/* Enhanced Track Context Menu */}
      <TrackContextMenu
        trackId={track.id}
        trackTitle={track.title}
        trackAlbumId={track.album_id}
        trackArtistName={track.artist}
        isFavorite={track.favorite || false}
        anchorPosition={contextMenuPosition}
        onClose={handleCloseContextMenu}
        onPlay={() => {
          onPlay(track.id);
          info(`Now playing: ${track.title}`);
        }}
        onAddToQueue={() => {
          success(`Added "${track.title}" to queue`);
          // TODO: Implement actual queue functionality
        }}
        onToggleFavorite={onToggleFavorite ? () => {
          onToggleFavorite(track.id);
          success(track.favorite ? `Removed "${track.title}" from favorites` : `Added "${track.title}" to favorites`);
        } : undefined}
        onShowAlbum={onShowAlbum && track.album_id ? () => {
          onShowAlbum(track.album_id!);
        } : undefined}
        onShowArtist={onShowArtist ? () => {
          onShowArtist(track.artist);
        } : undefined}
        onShowInfo={onShowInfo ? () => {
          onShowInfo(track.id);
        } : undefined}
        onEditMetadata={onEditMetadata ? () => {
          onEditMetadata(track.id);
        } : undefined}
        onDelete={onDelete ? () => {
          onDelete(track.id);
        } : undefined}
      />
    </>
  );
};

export default TrackRow;
