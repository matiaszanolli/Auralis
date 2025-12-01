import React from 'react';
import { Grid } from '@mui/material';
import { TrackCard } from '../../track/TrackCard';
// import TrackQueue from '../../player-bar-v2/queue/TrackQueue'; // FIXME: Component not found
import InfiniteScrollTrigger from '../Items/InfiniteScrollTrigger';
import { Track } from './TrackListView';

export interface TrackGridViewProps {
  tracks: Track[];
  hasMore: boolean;
  currentTrackId?: number;
  loadMoreRef: React.RefObject<HTMLDivElement>;
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
 */
export const TrackGridView: React.FC<TrackGridViewProps> = ({
  tracks,
  hasMore,
  currentTrackId,
  loadMoreRef,
  onTrackPlay,
  onRemoveTrack,
  onReorderQueue,
  onShuffleQueue,
  onClearQueue,
}) => {
  return (
    <>
      <Grid container spacing={3}>
        {tracks.map((track, index) => (
          <Grid
            item
            xs={12}
            sm={6}
            md={4}
            lg={3}
            key={track.id}
            className="animate-fade-in-up"
            sx={{
              animationDelay: `${index * 0.05}s`,
              animationFillMode: 'both',
            }}
          >
            <TrackCard
              id={track.id}
              title={track.title}
              artist={track.artist}
              album={track.album}
              albumId={track.album_id}
              duration={track.duration}
              albumArt={track.albumArt}
              onPlay={(id) => {
                const foundTrack = tracks.find((t) => t.id === id);
                if (foundTrack) {
                  onTrackPlay(foundTrack);
                }
              }}
            />
          </Grid>
        ))}
      </Grid>

      {/* Intersection observer trigger for infinite scroll */}
      {hasMore && <InfiniteScrollTrigger ref={loadMoreRef} />}

      {/* TrackQueue component removed - FIXME: Import path not found */}
      {/* TODO: Implement track queue display or remove if not needed */}
    </>
  );
};

export default TrackGridView;
