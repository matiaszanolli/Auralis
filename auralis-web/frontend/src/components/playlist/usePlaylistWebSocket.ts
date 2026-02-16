import { useEffect } from 'react';
import { useWebSocketContext } from '../../contexts/WebSocketContext';

interface UsePlaylistWebSocketProps {
  onPlaylistCreated: () => void;
  onPlaylistUpdated: (playlistId: number, updates: any) => void;
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

    // Subscribe to playlist_created
    const unsubscribeCreated = subscribe('playlist_created', () => {
      onPlaylistCreated();
    });

    // Subscribe to playlist_updated (handles all update actions)
    const unsubscribeUpdated = subscribe('playlist_updated', (message: any) => {
      try {
        const { playlist_id, action } = message.data;

        // For rename action, call onPlaylistUpdated callback
        if (action === 'renamed') {
          onPlaylistUpdated(playlist_id, { action });
        }
        // For track operations (add/remove/clear/reorder), trigger full refresh
        else if (action === 'track_added' || action === 'track_removed' || action === 'cleared' || action === 'reordered') {
          onPlaylistsRefresh();
        }
      } catch (err) {
        console.error('Error handling playlist_updated:', err);
      }
    });

    // Subscribe to playlist_deleted
    const unsubscribeDeleted = subscribe('playlist_deleted', (message: any) => {
      try {
        onPlaylistDeleted(message.data.playlist_id);
      } catch (err) {
        console.error('Error handling playlist_deleted:', err);
      }
    });

    // Cleanup: unsubscribe from all message types
    return () => {
      console.log('📝 PlaylistList: Cleaning up WebSocket subscriptions');
      unsubscribeCreated();
      unsubscribeUpdated();
      unsubscribeDeleted();
    };
  }, [subscribe, onPlaylistCreated, onPlaylistUpdated, onPlaylistDeleted, onPlaylistsRefresh]);
};
