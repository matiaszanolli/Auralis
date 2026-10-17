import { useCallback, useRef, useState } from 'react';
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

  // handleFindSimilar is passed to every library row, so it reads tracks
  // through a ref to keep a stable identity — a new callback per render
  // defeated the rows' memo on every page append and search keystroke
  // (#5660). Same pattern as toggleTrack in useTrackSelection.
  const tracksRef = useRef(tracks);
  tracksRef.current = tracks;

  const handleFindSimilar = useCallback((trackId: number) => {
    const track = tracksRef.current.find(t => t.id === trackId);
    setSimilarTrackId(trackId);
    setSimilarTrackTitle(track?.title || 'this track');
    setSimilarTracksModalOpen(true);
  }, []);

  // Only `open` flips on close (#5397). CozyLibraryView mounts the modal while
  // similarTrackId is set, so clearing the id and title here too unmounted it
  // before MUI's exit transition ran; they are replaced on the next open.
  const handleCloseSimilarTracksModal = useCallback(() => {
    setSimilarTracksModalOpen(false);
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
