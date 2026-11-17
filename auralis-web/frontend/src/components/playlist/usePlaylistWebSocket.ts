import { useEffect, useRef } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useMessageSubscriptions } from '@/hooks/websocket/useWebSocketMessages';
import type { PlaylistUpdatedMessage } from '@/types/websocket';

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
 * Subscriptions are owned by useMessageSubscriptions and cleaned up on unmount.
 */
export const usePlaylistWebSocket = ({
  onPlaylistCreated,
  onPlaylistUpdated,
  onPlaylistDeleted,
  onPlaylistsRefresh,
}: UsePlaylistWebSocketProps) => {
  const { subscribe, isConnected } = useWebSocketContext();

  // playlist_* events missed while the socket was down are never replayed: re-read the list when
  // the connection comes back (#6042).
  const wasConnectedRef = useRef(isConnected);
  useEffect(() => {
    if (isConnected && !wasConnectedRef.current) onPlaylistsRefresh();
    wasConnectedRef.current = isConnected;
  }, [isConnected, onPlaylistsRefresh]);

  // The shared helper keeps one subscription per type for the component's lifetime and reads the
  // latest handlers through a ref, so a caller passing inline closures no longer resubscribes every
  // render (#6041).
  useMessageSubscriptions(subscribe, {
    playlist_created: () => {
      onPlaylistCreated();
    },
    playlist_updated: (message) => {
      try {
        const { playlist_id, action } = message.data;
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
    },
    playlist_deleted: (message) => {
      try {
        onPlaylistDeleted(message.data.playlist_id);
      } catch (err) {
        console.error('Error handling playlist_deleted:', err);
      }
    },
  });
};
