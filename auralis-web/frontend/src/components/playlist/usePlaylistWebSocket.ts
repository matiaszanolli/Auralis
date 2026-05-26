import { useEffect } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import type {
  PlaylistUpdatedMessage,
  PlaylistDeletedMessage,
} from '@/types/websocket';

interface UsePlaylistWebSocketProps {
  onPlaylistCreated: () => void;
  /** Called on rename. Receives the playlist id and the typed action payload. */
  onPlaylistUpdated: (
    playlistId: number,
    updates: { action: PlaylistUpdatedMessage['data']['action'] }
  ) => void;
  onPlaylistDeleted: (playlistId: number) => void;
  onPlaylistsRefresh: () => void;
}

/**
 * usePlaylistWebSocket - Handles WebSocket subscriptions for playlist updates
 *
 * Subscribes to real-time playlist events:
 * - playlist_created
 * - playlist_updated (with actions: renamed, track_added, track_removed, reordered, cleared)
 * - playlist_deleted
 *
 * #3592: typed message payloads via the existing PlaylistUpdatedMessage /
 * PlaylistDeletedMessage interfaces so backend payload-shape changes surface
 * as TS errors instead of silent runtime failures.
 *
 * Automatically cleans up subscriptions on unmount.
 */
export const usePlaylistWebSocket = ({
  onPlaylistCreated,
  onPlaylistUpdated,
  onPlaylistDeleted,
  onPlaylistsRefresh,
}: UsePlaylistWebSocketProps) => {
  const { subscribe } = useWebSocketContext();

  useEffect(() => {
    console.log('📝 PlaylistList: Setting up WebSocket subscriptions');

    const unsubscribeCreated = subscribe('playlist_created', () => {
      onPlaylistCreated();
    });

    const unsubscribeUpdated = subscribe('playlist_updated', (message) => {
      try {
        const msg = message as PlaylistUpdatedMessage;
        const { playlist_id, action } = msg.data;
        if (action === 'renamed') {
          onPlaylistUpdated(playlist_id, { action });
        } else if (
          action === 'track_added' ||
          action === 'track_removed' ||
          action === 'cleared' ||
          action === 'reordered'
        ) {
          onPlaylistsRefresh();
        }
      } catch (err) {
        console.error('Error handling playlist_updated:', err);
      }
    });

    const unsubscribeDeleted = subscribe('playlist_deleted', (message) => {
      try {
        const msg = message as PlaylistDeletedMessage;
        onPlaylistDeleted(msg.data.playlist_id);
      } catch (err) {
        console.error('Error handling playlist_deleted:', err);
      }
    });

    return () => {
      console.log('📝 PlaylistList: Cleaning up WebSocket subscriptions');
      unsubscribeCreated();
      unsubscribeUpdated();
      unsubscribeDeleted();
    };
  }, [subscribe, onPlaylistCreated, onPlaylistUpdated, onPlaylistDeleted, onPlaylistsRefresh]);
};
