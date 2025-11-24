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
 * - playlist_updated
 * - playlist_deleted
 * - playlist_tracks_added
 * - playlist_track_removed
 * - playlist_cleared
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

    // Subscribe to playlist_updated
    const unsubscribeUpdated = subscribe('playlist_updated', (message: any) => {
      try {
        onPlaylistUpdated(message.data.playlist_id, message.data.updates);
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

    // Subscribe to playlist_tracks_added
    const unsubscribeTracksAdded = subscribe('playlist_tracks_added', () => {
      onPlaylistsRefresh();
    });

    // Subscribe to playlist_track_removed
    const unsubscribeTrackRemoved = subscribe('playlist_track_removed', () => {
      onPlaylistsRefresh();
    });

    // Subscribe to playlist_cleared
    const unsubscribeCleared = subscribe('playlist_cleared', () => {
      onPlaylistsRefresh();
    });

    // Cleanup: unsubscribe from all message types
    return () => {
      console.log('📝 PlaylistList: Cleaning up WebSocket subscriptions');
      unsubscribeCreated();
      unsubscribeUpdated();
      unsubscribeDeleted();
      unsubscribeTracksAdded();
      unsubscribeTrackRemoved();
      unsubscribeCleared();
    };
  }, [subscribe, onPlaylistCreated, onPlaylistUpdated, onPlaylistDeleted, onPlaylistsRefresh]);
};
