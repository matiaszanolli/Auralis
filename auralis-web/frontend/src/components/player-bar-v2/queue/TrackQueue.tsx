/**
 * TrackQueue Component (Refactored)
 *
 * Displays upcoming tracks in queue with context menu support.
 * Refactored from 234 lines using extracted components and helpers.
 *
 * Extracted modules:
 * - TrackQueueStyles - All styled components
 * - TrackQueueHelpers - Utility functions
 * - useTrackQueueMenu - Context menu state
 * - TrackQueueItem - Individual track item component
 */

import React from 'react';
import { ContextMenu, getTrackContextActions } from '../../shared/ContextMenu';
import { useContextMenu } from '../../shared/ContextMenu';
import { useToast } from '../../shared/ui/feedback';
import { QueueContainer, QueueHeader, QueueList } from './TrackQueueStyles';
import { TrackQueueItem } from './TrackQueueItem';
import { useTrackQueueMenu } from './useTrackQueueMenu';

interface Track {
  id: number;
  title: string;
  artist?: string;
  duration: number;
}

interface TrackQueueProps {
  tracks: Track[];
  currentTrackId?: number;
  onTrackClick?: (trackId: number) => void;
  title?: string;
}

/**
 * TrackQueue - Main orchestrator component
 *
 * Manages:
 * - Queue container and header
 * - Track item list with context menu
 * - Track selection and playback
 */
export const TrackQueue: React.FC<TrackQueueProps> = ({
  tracks,
  currentTrackId,
  onTrackClick,
  title = 'Queue',
}) => {
  const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();
  const { success, info } = useToast();
  const { selectedTrackId, handleTrackContextMenu } = useTrackQueueMenu();

  if (!tracks || tracks.length === 0) {
    return null;
  }

  // Get selected track for context menu
  const selectedTrack = tracks.find(t => t.id === selectedTrackId);

  // Context menu actions
  const contextActions = selectedTrack ? getTrackContextActions(
    selectedTrack.id,
    false,
    {
      onPlay: () => {
        onTrackClick?.(selectedTrack.id);
        info(`Now playing: ${selectedTrack.title}`);
      },
      onAddToQueue: () => {
        success(`Added "${selectedTrack.title}" to queue`);
      },
      onToggleLove: () => {
        success(`Added "${selectedTrack.title}" to favorites`);
      },
      onAddToPlaylist: () => {
        info('Select playlist');
      },
      onShowInfo: () => {
        const artist = selectedTrack.artist ? `by ${selectedTrack.artist}` : '';
        info(`${selectedTrack.title} ${artist}`);
      },
    }
  ) : [];

  return (
    <QueueContainer>
      <QueueHeader>{title}</QueueHeader>
      <QueueList>
        {tracks.map((track, index) => (
          <TrackQueueItem
            key={track.id}
            track={track}
            index={index}
            isActive={currentTrackId === track.id}
            onTrackClick={onTrackClick || (() => {})}
            onContextMenu={(e, t) =>
              handleTrackContextMenu(e, t, handleContextMenu)
            }
          />
        ))}
      </QueueList>

      <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={handleCloseContextMenu}
        actions={contextActions}
      />
    </QueueContainer>
  );
};

export default TrackQueue;
