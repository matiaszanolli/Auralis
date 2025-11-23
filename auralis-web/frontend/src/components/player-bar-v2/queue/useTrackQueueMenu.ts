/**
 * useTrackQueueMenu Hook
 *
 * Manages context menu state for queue tracks
 */

import { useState } from 'react';

interface Track {
  id: number;
  title: string;
  artist?: string;
  duration: number;
}

export const useTrackQueueMenu = () => {
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null);

  const handleTrackContextMenu = (e: React.MouseEvent, track: Track, onContextMenu: (e: React.MouseEvent) => void) => {
    e.preventDefault();
    e.stopPropagation();
    setSelectedTrackId(track.id);
    onContextMenu(e);
  };

  return {
    selectedTrackId,
    setSelectedTrackId,
    handleTrackContextMenu,
  };
};
