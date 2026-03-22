/**
 * TrackTableRowItem - Individual track row in album table
 */

import React from 'react';
import { TableCell, Typography, IconButton } from '@mui/material';
import { MoreVert } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { StyledTableRow } from '@/components/library/Styles/Table.styles';
import { TrackPlayIndicator } from '@/components/library/Items/tracks/TrackPlayIndicator';
import { ContextMenu } from '@/components/shared/ContextMenu';
import { useTrackContextMenu } from '@/components/library/Items/tracks/useTrackContextMenu';

import type { DetailTrack as Track } from '@/types/domain';

interface TrackTableRowItemProps {
  track: Track;
  index: number;
  isCurrentTrack: boolean;
  isPlaying: boolean;
  onTrackClick: (track: Track) => void;
  onFindSimilar?: (trackId: number) => void; // Phase 5: Find similar tracks
  formatDuration: (seconds: number) => string;
}

export const TrackTableRowItem = ({
  track,
  index,
  isCurrentTrack,
  isPlaying,
  onTrackClick,
  onFindSimilar,
  formatDuration,
}: TrackTableRowItemProps) => {
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
    onPlay: (_trackId) => onTrackClick(track),
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
        trackNumber={track.trackNumber ?? undefined}
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
          aria-label={`More options for ${track.title}`}
          sx={{
            opacity: 0,
            transition: tokens.transitions.fast,
            '.MuiTableRow-root:hover &, &:focus-visible': {
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
