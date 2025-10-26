import React, { useState } from 'react';
import { Box, Typography, IconButton, styled } from '@mui/material';
import { PlayArrow, Pause, MoreVert, MusicNote } from '@mui/icons-material';
import { colors, gradients, spacing, borderRadius, transitions } from '../../theme/auralisTheme';
import { useContextMenu, ContextMenu, getTrackContextActions } from '../shared/ContextMenu';
import { useToast } from '../shared/Toast';

export interface Track {
  id: number;
  title: string;
  artist: string;
  album?: string;
  duration: number;
  albumArt?: string;
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
}

const RowContainer = styled(Box)<{ iscurrent?: string }>(({ iscurrent }) => ({
  display: 'flex',
  alignItems: 'center',
  height: '48px',
  padding: `0 ${spacing.md}px`,
  borderRadius: `${borderRadius.xs}px`,
  cursor: 'pointer',
  transition: `all ${transitions.fast}`,
  background: iscurrent === 'true' ? 'rgba(102, 126, 234, 0.12)' : 'transparent',
  border: iscurrent === 'true' ? '1px solid rgba(102, 126, 234, 0.2)' : '1px solid transparent',
  position: 'relative',
  marginBottom: `${spacing.xs / 2}px`,

  '&:hover': {
    background: iscurrent === 'true'
      ? 'rgba(102, 126, 234, 0.18)'
      : colors.background.hover,
    transform: 'translateX(4px)',

    '& .track-number': {
      opacity: 0,
    },

    '& .play-button': {
      opacity: 1,
    },

    '& .more-button': {
      opacity: 1,
    },
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
  transition: `opacity ${transitions.fast}`,
}));

const PlayButton = styled(IconButton)({
  position: 'absolute',
  width: '32px',
  height: '32px',
  opacity: 0,
  transition: `opacity ${transitions.fast}`,
  color: '#667eea',

  '&:hover': {
    background: 'rgba(102, 126, 234, 0.12)',
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

  '& img': {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
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
}) => {
  const [imageError, setImageError] = useState(false);
  const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();
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
    handleContextMenu(e);
  };

  const handleTrackContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    handleContextMenu(e);
  };

  // Context menu actions
  const contextActions = getTrackContextActions(
    track.id,
    false, // isLoved - can be extended with user favorites state
    {
      onPlay: () => {
        onPlay(track.id);
        info(`Now playing: ${track.title}`);
      },
      onAddToQueue: () => {
        success(`Added "${track.title}" to queue`);
      },
      onLove: () => {
        success(`Added "${track.title}" to favorites`);
      },
      onAddToPlaylist: () => {
        info('Select playlist'); // TODO: Show playlist selector modal
      },
      onEditMetadata: onEditMetadata ? () => {
        onEditMetadata(track.id);
      } : undefined,
      onShowAlbum: () => {
        info(`Album: ${track.album || 'Unknown'}`);
      },
      onShowArtist: () => {
        info(`Artist: ${track.artist}`);
      },
      onShowInfo: () => {
        info(`${track.title} by ${track.artist}`);
      },
    }
  );

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

      {/* Context Menu */}
      <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={handleCloseContextMenu}
        actions={contextActions}
      />
    </>
  );
};

export default TrackRow;
