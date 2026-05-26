import { useCallback, useMemo } from 'react';
import Grid2 from '@mui/material/Unstable_Grid2';
import { TrackCard } from '@/components/track/TrackCard';
import type { LibraryTrack as Track } from '@/types/domain';

export interface TrackGridViewProps {
  tracks: Track[];
  hasMore: boolean;
  currentTrackId?: number;
  onTrackPlay: (track: Track) => void;
  onRemoveTrack: (index: number) => Promise<void>;
  onReorderQueue: (newOrder: number[]) => Promise<void>;
  onShuffleQueue: () => Promise<void>;
  onClearQueue: () => Promise<void>;
}

/**
 * TrackGridView - Grid layout for track cards
 *
 * Displays tracks as cards with album art and queue management.
 * Infinite scroll is handled by the parent (TrackListView) via
 * react-infinite-scroll-component.
 *
 * #3576: An id→Track index is built once per `tracks` change so the per-card
 * onPlay callback can be a stable, O(1) lookup `useCallback` instead of an
 * inline arrow doing `tracks.find(...)` per click. The stable identity also
 * preserves `TrackCard`'s `React.memo` across renders. Full virtualization is
 * tracked separately by the audit.
 */
export const TrackGridView = ({
  tracks,
  currentTrackId: _currentTrackId,
  onTrackPlay,
  onRemoveTrack: _onRemoveTrack,
  onReorderQueue: _onReorderQueue,
  onShuffleQueue: _onShuffleQueue,
  onClearQueue: _onClearQueue,
}: TrackGridViewProps) => {
  const trackById = useMemo(() => {
    const map = new Map<number, Track>();
    for (const track of tracks) map.set(track.id, track);
    return map;
  }, [tracks]);

  const handlePlay = useCallback(
    (id: number) => {
      const found = trackById.get(id);
      if (found) onTrackPlay(found);
    },
    [trackById, onTrackPlay]
  );

  return (
    <Grid2 container spacing={3}>
      {tracks.map((track, index) => (
        <Grid2
          xs={12}
          sm={6}
          md={4}
          lg={3}
          key={track.id}
          className="animate-fade-in-up"
          sx={
            index < 10
              ? {
                  animationDelay: `${index * 0.05}s`,
                  animationFillMode: 'both',
                }
              : undefined
          }
        >
          <TrackCard
            id={track.id}
            title={track.title}
            artist={track.artist}
            album={track.album}
            albumId={track.albumId ?? undefined}
            duration={track.duration}
            albumArt={track.artworkUrl ?? undefined}
            onPlay={handlePlay}
          />
        </Grid2>
      ))}
    </Grid2>
  );
};

export default TrackGridView;
