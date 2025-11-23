/**
 * SimilarTracks Component
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Displays similar tracks based on 25D audio fingerprint similarity
 *
 * Features:
 * - Shows similar tracks in a compact list
 * - Similarity percentage badges
 * - Click to play similar track
 * - Loading and error states
 * - Empty state when no similar tracks
 */

import React from 'react';
import { useSimilarTracksLoader } from './useSimilarTracksLoader';
import { useSimilarTracksFormatting } from './useSimilarTracksFormatting';
import SimilarTracksLoadingState from './SimilarTracksLoadingState';
import SimilarTracksErrorState from './SimilarTracksErrorState';
import SimilarTracksEmptyState from './SimilarTracksEmptyState';
import SimilarTracksList from './SimilarTracksList';

interface SimilarTracksProps {
  /** Current track ID to find similar tracks for */
  trackId: number | null;
  /** Callback when user clicks on a similar track */
  onTrackSelect?: (trackId: number) => void;
  /** Number of similar tracks to show (default: 5) */
  limit?: number;
  /** Use pre-computed K-NN graph (default: true) */
  useGraph?: boolean;
}

const SimilarTracks: React.FC<SimilarTracksProps> = ({
  trackId,
  onTrackSelect,
  limit = 5,
  useGraph = true
}) => {
  // Load similar tracks
  const { similarTracks, loading, error } = useSimilarTracksLoader({
    trackId,
    limit,
    useGraph,
  });

  // Formatting utilities
  const { getSimilarityColor, formatDuration } = useSimilarTracksFormatting();

  // Loading state
  if (loading) {
    return <SimilarTracksLoadingState />;
  }

  // Error state
  if (error) {
    return <SimilarTracksErrorState error={error} />;
  }

  // Empty state - no track selected or no results
  if (!trackId || similarTracks.length === 0) {
    return <SimilarTracksEmptyState trackId={trackId} />;
  }

  // Similar tracks list
  return (
    <SimilarTracksList
      tracks={similarTracks}
      useGraph={useGraph}
      onTrackSelect={onTrackSelect || (() => {})}
      getSimilarityColor={getSimilarityColor}
      formatDuration={formatDuration}
    />
  );
};

export default SimilarTracks;
