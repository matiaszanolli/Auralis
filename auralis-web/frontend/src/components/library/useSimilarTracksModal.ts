import { useCallback, useState } from 'react';
import type { LibraryTrack as Track } from '@/types/domain';

interface UseSimilarTracksModalArgs {
  tracks: Track[];
  onPlayTrack: (track: Track) => void;
}

/**
 * useSimilarTracksModal - "Find similar tracks" modal state
 *
 * Extracted from CozyLibraryView.tsx (#4456) to keep the orchestrator under
 * the 300-line guideline; follows the same extraction pattern as
 * useBatchOperations / useNavigationState / useMetadataEditing / usePlaybackState.
 */
export const useSimilarTracksModal = ({ tracks, onPlayTrack }: UseSimilarTracksModalArgs) => {
  const [similarTracksModalOpen, setSimilarTracksModalOpen] = useState(false);
  const [similarTrackId, setSimilarTrackId] = useState<number | null>(null);
  const [similarTrackTitle, setSimilarTrackTitle] = useState<string>('');

  const handleFindSimilar = useCallback((trackId: number) => {
    const track = tracks.find(t => t.id === trackId);
    setSimilarTrackId(trackId);
    setSimilarTrackTitle(track?.title || 'this track');
    setSimilarTracksModalOpen(true);
  }, [tracks]);

  const handleCloseSimilarTracksModal = useCallback(() => {
    setSimilarTracksModalOpen(false);
    setSimilarTrackId(null);
    setSimilarTrackTitle('');
  }, []);

  // #3617: stable onTrackPlay for SimilarTracksModal — was an inline arrow
  // that defeated memoization if the modal is ever wrapped in React.memo.
  const handlePlaySimilarTrack = useCallback(
    (trackId: number) => {
      const track = tracks.find(t => t.id === trackId);
      if (track) onPlayTrack(track);
    },
    [tracks, onPlayTrack]
  );

  return {
    similarTracksModalOpen,
    similarTrackId,
    similarTrackTitle,
    handleFindSimilar,
    handleCloseSimilarTracksModal,
    handlePlaySimilarTrack,
  };
};
