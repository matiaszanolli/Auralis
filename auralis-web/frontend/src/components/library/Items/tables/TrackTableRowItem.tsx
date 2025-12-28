/**
 * TrackTableRowItem - Individual track row in album table
 */

import React from 'react';
import { TableCell, Typography, IconButton } from '@mui/material';
import { MoreVert } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { StyledTableRow } from '../../Styles/Table.styles';
import { TrackPlayIndicator } from '../tracks/TrackPlayIndicator';
import { ContextMenu } from '../../../shared/ContextMenu';
import { useTrackContextMenu } from '../tracks/useTrackContextMenu';

interface Track {
  id: number;
  title: string;
  artist: string;
  duration: number;
  track_number?: number;
  disc_number?: number;
  album_id?: number;
  favorite?: boolean;
}

interface TrackTableRowItemProps {
  track: Track;
  index: number;
  isCurrentTrack: boolean;
  isPlaying: boolean;
  onTrackClick: (track: Track) => void;
  onFindSimilar?: (trackId: number) => void; // Phase 5: Find similar tracks
  formatDuration: (seconds: number) => string;
}

export const TrackTableRowItem: React.FC<TrackTableRowItemProps> = ({
  track,
  index,
  isCurrentTrack,
  isPlaying,
  onTrackClick,
  onFindSimilar,
  formatDuration,
}) => {
  // Context menu support (Phase 5)
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
    onPlay: (trackId) => onTrackClick(track),
    onFindSimilar,
  });

  return (
    <>
      <StyledTableRow
        onClick={() => onTrackClick(track)}
        onContextMenu={handleTrackContextMenu}
        className={isCurrentTrack ? 'current-track' : ''}
      >
      <TrackPlayIndicator
        isCurrentTrack={isCurrentTrack}
        isPlaying={isPlaying}
        trackNumber={track.track_number}
        index={index}
      />
      <TableCell>
        <Typography
          className="track-title"
          sx={{
            fontSize: tokens.typography.fontSize.md,
            fontWeight: isCurrentTrack ? tokens.typography.fontWeight.semibold : tokens.typography.fontWeight.normal,
            color: isCurrentTrack ? tokens.colors.accent.primary : tokens.colors.text.primary,
          }}
        >
          {track.title}
        </Typography>
      </TableCell>
      <TableCell>
        <Typography sx={{
          fontSize: tokens.typography.fontSize.sm,
          color: tokens.colors.text.secondary,
        }}>
          {track.artist}
        </Typography>
      </TableCell>
      <TableCell align="right">
        <Typography sx={{
          fontSize: tokens.typography.fontSize.sm,
          color: tokens.colors.text.tertiary,
          fontFamily: tokens.typography.fontFamily.mono,
        }}>
          {formatDuration(track.duration)}
        </Typography>
      </TableCell>
      <TableCell align="right" onClick={(e) => e.stopPropagation()}>
        <IconButton
          size="small"
          onClick={handleMoreClick}
          sx={{
            opacity: 0,
            transition: tokens.transitions.fast,
            '.MuiTableRow-root:hover &': {
              opacity: 1,
            },
            color: tokens.colors.text.secondary,
            '&:hover': {
              backgroundColor: tokens.colors.bg.tertiary,
              color: tokens.colors.accent.primary,
            },
          }}
        >
          <MoreVert fontSize="small" />
        </IconButton>
      </TableCell>
    </StyledTableRow>

    {/* Context Menu */}
    <ContextMenu
      open={Boolean(contextMenuPosition)}
      anchorPosition={contextMenuPosition || undefined}
      onClose={handleCloseContextMenu}
      actions={contextActions}
      trackId={track.id}
      trackTitle={track.title}
      playlists={playlists}
      isLoadingPlaylists={isLoadingPlaylists}
      onPlaylistsLoad={() => {}}
      onAddToPlaylist={handleAddToPlaylist}
      onCreatePlaylist={handleCreatePlaylist}
    />
    </>
  );
};

export default TrackTableRowItem;
