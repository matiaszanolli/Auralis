/**
 * TrackTableRowItem - Individual track row in album table
 */

import { KeyboardEvent, memo } from 'react';
import { TableCell, Typography, IconButton } from '@mui/material';
import MoreVert from '@mui/icons-material/MoreVert';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
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

const TrackTableRowItemImpl = ({
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
        tabIndex={0}
        aria-label={`Play ${track.title}`}
        onKeyDown={(e: KeyboardEvent) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onTrackClick(track);
          }
        }}
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
            color: isCurrentTrack ? themeVars.accent : themeVars.textPrimary,
          }}
        >
          {track.title}
        </Typography>
      </TableCell>
      <TableCell>
        <Typography sx={{
          fontSize: tokens.typography.fontSize.sm,
          color: themeVars.textSecondary,
        }}>
          {track.artist}
        </Typography>
      </TableCell>
      <TableCell align="right">
        <Typography sx={{
          fontSize: tokens.typography.fontSize.sm,
          color: themeVars.textMuted,
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
            color: themeVars.textSecondary,
            '&:hover': {
              backgroundColor: themeVars.surfaceSecondary,
              color: themeVars.accent,
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

/**
 * Memoized so a play/pause tick — which re-renders AlbumTrackTable and every
 * row under it — only re-renders the rows whose output actually changed
 * (#4472). Mirrors the QueueTrackItem (#4177) / AlbumCard (#3929) pattern and,
 * like them, relies on the parent passing stable handlers.
 *
 * `isPlaying` is deliberately compared only for the current track: the prop
 * reaches the DOM solely through `isCurrentTrack && isPlaying`
 * (TrackPlayIndicator), so for every other row a play/pause transition cannot
 * change what renders. Comparing it unconditionally would re-render all 20-30
 * rows on each toggle — the exact cost this memo exists to remove.
 */
export const TrackTableRowItem = memo(TrackTableRowItemImpl, (prev, next) =>
  prev.track === next.track &&
  prev.index === next.index &&
  prev.isCurrentTrack === next.isCurrentTrack &&
  (prev.isPlaying === next.isPlaying || (!prev.isCurrentTrack && !next.isCurrentTrack)) &&
  prev.onTrackClick === next.onTrackClick &&
  prev.onFindSimilar === next.onFindSimilar &&
  prev.formatDuration === next.formatDuration
);

export default TrackTableRowItem;
