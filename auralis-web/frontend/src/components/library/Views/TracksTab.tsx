
import { useRef, useState, useCallback } from 'react';
import { Table, TableBody, TableRow, TableCell, Typography } from '@mui/material';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useAppScrollElement } from '@/components/library/Items/utilities/useGridVirtualizer';
import { TracksTableContainer } from '@/components/library/Styles/ArtistDetail.styles';
import { usePlaybackState } from '@/components/library/usePlaybackState';
import TracksTableHeader from './TracksTableHeader';
import ArtistTrackRow from './ArtistTrackRow';
import useDurationFormatter from './useDurationFormatter';
import type { DetailTrack as Track } from '@/types/domain';

interface TracksTabProps {
  tracks: Track[];
  onTrackClick: (track: Track) => void;
}

// Seeds the window before a row has been measured; every row is one line of the same height.
const ESTIMATED_ROW_HEIGHT = 56;
const OVERSCAN_ROWS = 12;

/**
 * TracksTab - Table of all tracks for artist detail view
 *
 * Displays:
 * - Track number/play indicator
 * - Track title (bold if current)
 * - Album name
 * - Duration in MM:SS format
 * - Empty state message
 *
 * Rows are windowed against the shared `#app-main-content-scroll` element with spacer rows above
 * and below, so an artist with thousands of tracks mounts a screenful of rows, not all of them
 * (#6023). Where layout cannot be measured (jsdom) every row renders.
 */
export const TracksTab = ({
  tracks,
  onTrackClick,
}: TracksTabProps) => {
  const { formatDuration } = useDurationFormatter();
  // Read playback state from Redux directly instead of prop-drilling (#4154).
  const { currentTrackId, isPlaying } = usePlaybackState();

  const containerRef = useRef<HTMLDivElement>(null);
  const scrollElement = useAppScrollElement();
  const [rowHeight, setRowHeight] = useState(ESTIMATED_ROW_HEIGHT);
  const count = tracks?.length ?? 0;

  // One measured row stands for all of them; a spacer error is only a scroll-bar jitter.
  const measureRow = useCallback((element: HTMLTableRowElement | null) => {
    const height = element?.getBoundingClientRect().height ?? 0;
    if (height > 0) setRowHeight((previous) => (Math.abs(previous - height) < 1 ? previous : height));
  }, []);

  const virtualizer = useVirtualizer({
    count,
    getScrollElement: () => scrollElement,
    estimateSize: () => rowHeight,
    overscan: OVERSCAN_ROWS,
    scrollMargin: containerRef.current?.offsetTop ?? 0,
  });

  if (!tracks || tracks.length === 0) {
    return (
      <TableRow>
        <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
          <Typography sx={{
            color: "text.secondary"
          }}>
            No tracks found for this artist
          </Typography>
        </TableCell>
      </TableRow>
    );
  }

  const windowed = scrollElement !== null ? virtualizer.getVirtualItems() : null;
  const firstIndex = windowed?.[0]?.index ?? 0;
  const lastIndex = windowed ? (windowed[windowed.length - 1]?.index ?? -1) : count - 1;
  const visible = tracks.slice(firstIndex, lastIndex + 1);
  const spacerBefore = windowed ? firstIndex * rowHeight : 0;
  const spacerAfter = windowed ? Math.max(0, (count - 1 - lastIndex) * rowHeight) : 0;

  return (
    <TracksTableContainer ref={containerRef}>
      <Table>
        <TracksTableHeader />
        <TableBody>
          {spacerBefore > 0 && <TableRow aria-hidden style={{ height: spacerBefore }}><TableCell colSpan={4} sx={{ p: 0, border: 0 }} /></TableRow>}
          {visible.map((track, offset) => {
            const index = firstIndex + offset;
            const isCurrentTrack = currentTrackId === track.id;
            return (
              <ArtistTrackRow
                key={track.id}
                rowRef={offset === 0 ? measureRow : undefined}
                track={track}
                index={index}
                isCurrentTrack={isCurrentTrack}
                // A row reads isPlaying only when it is the current track; handing the global flag to
                // every row changed their props on each play/pause and defeated memo (#6023).
                isPlaying={isCurrentTrack && isPlaying}
                onTrackClick={onTrackClick}
                formatDuration={formatDuration}
              />
            );
          })}
          {spacerAfter > 0 && <TableRow aria-hidden style={{ height: spacerAfter }}><TableCell colSpan={4} sx={{ p: 0, border: 0 }} /></TableRow>}
        </TableBody>
      </Table>
    </TracksTableContainer>
  );
};

export default TracksTab;
