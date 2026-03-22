import Grid2 from '@mui/material/Unstable_Grid2';
import { TrackCard } from '../../track/TrackCard';
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
 * Infinite scroll is handled by the parent (TrackListView) via react-infinite-scroll-component.
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
  return (
    <Grid2 container spacing={3}>
      {tracks.map((track, index) => (
        <Grid2 xs={12}
          sm={6}
          md={4}
          lg={3}
          key={track.id}
          className="animate-fade-in-up"
          sx={index < 10 ? {
            animationDelay: `${index * 0.05}s`,
            animationFillMode: 'both',
          } : undefined}
        >
          <TrackCard
            id={track.id}
            title={track.title}
            artist={track.artist}
            album={track.album}
            albumId={track.albumId ?? undefined}
            duration={track.duration}
            albumArt={track.artworkUrl ?? undefined}
            onPlay={(id) => {
              const foundTrack = tracks.find((t) => t.id === id);
              if (foundTrack) {
                onTrackPlay(foundTrack);
              }
            }}
          />
        </Grid2>
      ))}
    </Grid2>
  );
};

export default TrackGridView;
