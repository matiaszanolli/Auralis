/**
 * TrackListView - Track List Rendering Component
 *
 * Handles rendering of tracks in either grid or list view mode.
 * Includes infinite scroll support and loading states.
 *
 * Extracted from CozyLibraryView.tsx for better separation of concerns.
 *
 * Features:
 * - Grid view with album cards
 * - List view with selectable track rows
 * - Infinite scroll with Intersection Observer
 * - Loading skeletons
 * - Virtual spacers for proper scrollbar length
 * - Queue integration
 */

import React, { useRef, useEffect } from 'react';
import { Box, Grid, Paper, Typography } from '@mui/material';
import { TrackCard } from '../track/TrackCard';
import SelectableTrackRow from './SelectableTrackRow';
import TrackQueue from '../player/TrackQueue';
import { LibraryGridSkeleton, TrackRowSkeleton } from '../shared/SkeletonLoader';
import * as queueService from '../../services/queueService';
import { useToast } from '../shared/Toast';

export interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  album_id?: number;
  duration: number;
  albumArt?: string;
  quality?: number;
  isEnhanced?: boolean;
  genre?: string;
  year?: number;
}

export type ViewMode = 'grid' | 'list';

export interface TrackListViewProps {
  tracks: Track[];
  viewMode: ViewMode;
  loading: boolean;
  hasMore: boolean;
  totalTracks: number;
  isLoadingMore: boolean;
  currentTrackId?: number;
  isPlaying: boolean;

  // Selection (for list view)
  selectedTracks: Set<number>;
  isSelected: (trackId: number) => boolean;
  onToggleSelect: (trackId: number, e: React.MouseEvent) => void;

  // Actions
  onTrackPlay: (track: Track) => void;
  onPause: () => void;
  onEditMetadata: (trackId: number) => void;
  onLoadMore: () => void;
}

/**
 * Track List View Component
 *
 * Renders tracks in grid or list mode with infinite scroll support.
 */
export const TrackListView: React.FC<TrackListViewProps> = ({
  tracks,
  viewMode,
  loading,
  hasMore,
  totalTracks,
  isLoadingMore,
  currentTrackId,
  isPlaying,
  selectedTracks,
  isSelected,
  onToggleSelect,
  onTrackPlay,
  onPause,
  onEditMetadata,
  onLoadMore
}) => {
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const { success, error, info } = useToast();

  // Infinite scroll with Intersection Observer
  useEffect(() => {
    if (!loadMoreRef.current) return;

    // Debounce flag to prevent multiple simultaneous loads
    let isObserverLoading = false;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoadingMore && !loading && !isObserverLoading) {
          isObserverLoading = true;
          onLoadMore();
          // Reset after a delay to prevent rapid refiring
          setTimeout(() => {
            isObserverLoading = false;
          }, 500);
        }
      },
      { threshold: 0.1, rootMargin: '100px' } // Load when 100px away from trigger
    );

    observer.observe(loadMoreRef.current);

    return () => {
      observer.disconnect();
      isObserverLoading = false;
    };
  }, [hasMore, isLoadingMore, loading, onLoadMore]);

  // Show loading skeletons
  if (loading) {
    return viewMode === 'grid' ? (
      <LibraryGridSkeleton count={12} />
    ) : (
      <Paper
        elevation={2}
        sx={{
          background: 'rgba(255,255,255,0.05)',
          borderRadius: 3,
          overflow: 'hidden',
          p: 2
        }}
      >
        {Array.from({ length: 8 }).map((_, index) => (
          <TrackRowSkeleton key={index} />
        ))}
      </Paper>
    );
  }

  // Grid View
  if (viewMode === 'grid') {
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
                animationFillMode: 'both'
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
                  const track = tracks.find(t => t.id === id);
                  if (track) {
                    onTrackPlay(track);
                  }
                }}
              />
            </Grid>
          ))}
        </Grid>

        {/* Intersection observer trigger for infinite scroll */}
        {hasMore && (
          <Box
            ref={loadMoreRef}
            sx={{
              height: '1px',
              width: '100%',
              pointerEvents: 'auto'
            }}
          />
        )}

        {/* Virtual spacer for proper scrollbar length in grid view */}
        {hasMore && totalTracks > tracks.length && (
          <Box
            sx={{
              height: `${Math.ceil((totalTracks - tracks.length) / 4) * 240}px`, // 4 cols (lg), ~240px per row
              pointerEvents: 'none'
            }}
          />
        )}

        {/* Track Queue - Shows current album/playlist tracks */}
        {tracks.length > 0 && (
          <TrackQueue
            tracks={tracks.map(t => ({
              id: t.id,
              title: t.title,
              artist: t.artist,
              duration: t.duration
            }))}
            currentTrackId={currentTrackId}
            onTrackClick={(trackId) => {
              const track = tracks.find(t => t.id === trackId);
              if (track) {
                onTrackPlay(track);
              }
            }}
            onRemoveTrack={async (index) => {
              try {
                await queueService.removeTrackFromQueue(index);
                info('Track removed from queue');
              } catch (err) {
                error('Failed to remove track from queue');
              }
            }}
            onReorderQueue={async (newOrder) => {
              try {
                await queueService.reorderQueue(newOrder);
                success('Queue reordered');
              } catch (err) {
                error('Failed to reorder queue');
              }
            }}
            onShuffleQueue={async () => {
              try {
                await queueService.shuffleQueue();
                success('Queue shuffled');
              } catch (err) {
                error('Failed to shuffle queue');
              }
            }}
            onClearQueue={async () => {
              try {
                await queueService.clearQueue();
                info('Queue cleared');
              } catch (err) {
                error('Failed to clear queue');
              }
            }}
            title="Current Queue"
          />
        )}
      </>
    );
  }

  // List View
  return (
    <Paper
      elevation={2}
      sx={{
        background: 'rgba(255,255,255,0.05)',
        borderRadius: 3,
        overflow: 'hidden',
        p: 2
      }}
    >
      {tracks.map((track, index) => (
        <Box
          key={track.id}
          className="animate-fade-in-left"
          sx={{
            animationDelay: `${index * 0.03}s`,
            animationFillMode: 'both'
          }}
        >
          <SelectableTrackRow
            track={track}
            index={index}
            isSelected={isSelected(track.id)}
            onToggleSelect={(e) => onToggleSelect(track.id, e)}
            isPlaying={isPlaying}
            isCurrent={currentTrackId === track.id}
            onPlay={(trackId) => {
              const track = tracks.find(t => t.id === trackId);
              if (track) {
                onTrackPlay(track);
              }
            }}
            onPause={onPause}
            onEditMetadata={onEditMetadata}
          />
        </Box>
      ))}

      {/* Intersection observer trigger for infinite scroll */}
      {hasMore && (
        <Box
          ref={loadMoreRef}
          sx={{
            height: '1px',
            width: '100%',
            pointerEvents: 'auto'
          }}
        />
      )}

      {/* Virtual spacer for proper scrollbar length */}
      {hasMore && totalTracks > tracks.length && (
        <Box
          sx={{
            height: `${(totalTracks - tracks.length) * 72}px`, // 72px avg row height
            pointerEvents: 'none'
          }}
        />
      )}

      {/* Infinite scroll loading indicator */}
      {isLoadingMore && (
        <Box
          sx={{
            p: 3,
            textAlign: 'center',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2
          }}
        >
          <Box
            sx={{
              width: 20,
              height: 20,
              border: '2px solid',
              borderColor: 'primary.main',
              borderRightColor: 'transparent',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              '@keyframes spin': {
                '0%': { transform: 'rotate(0deg)' },
                '100%': { transform: 'rotate(360deg)' }
              }
            }}
          />
          <Typography variant="body2" color="text.secondary">
            Loading more tracks... ({tracks.length}/{totalTracks})
          </Typography>
        </Box>
      )}

      {/* End of list indicator */}
      {!hasMore && tracks.length > 0 && (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Showing all {totalTracks} tracks
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

export default TrackListView;
