/**
 * useLibraryChangeSync — keep the React Query library caches current (#5871)
 *
 * `library_updated` was consumed only by useLibraryWithStats (track list and
 * stats) and nothing invalidated `['albums']`, so under the 5-minute
 * staleTime the album grid kept the pre-scan set after a scan (removed albums
 * still clickable, then a 404 on open) and pre-edit titles/years after a
 * metadata edit. Mounted once, app-wide; the artist list refreshes its own
 * hook-local state on the same frames (CozyArtistList).
 *
 * @module hooks/library/useLibraryChangeSync
 */

import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import type { MessageOf } from '@/contexts/WebSocketContext';

type LibraryChangeMessageType =
  | 'library_updated'
  | 'metadata_updated'
  | 'metadata_batch_updated'
  | 'library_tracks_removed';

/** Frames after which library browse data (albums, artists) may be stale. */
export const LIBRARY_CHANGE_MESSAGES: LibraryChangeMessageType[] = [
  'library_updated',
  'metadata_updated',
  'metadata_batch_updated',
  'library_tracks_removed',
];

export function useLibraryChangeSync(): void {
  const queryClient = useQueryClient();

  const handleChange = useCallback(
    (message: MessageOf<LibraryChangeMessageType>) => {
      // Active queries refetch every loaded page in place; inactive ones are
      // marked stale and refetch when next mounted.
      void queryClient.invalidateQueries({ queryKey: ['albums'] });
      // A scan or a removal changes which tracks (and so which albums) carry
      // fingerprints; a tag edit does not. A cached "none yet" (null) would
      // otherwise keep tiles on the hash gradient for the whole staleTime.
      if (message.type === 'library_updated' || message.type === 'library_tracks_removed') {
        void queryClient.invalidateQueries({ queryKey: ['album-fingerprint'] });
      }
    },
    [queryClient]
  );

  useWebSocketMessages(LIBRARY_CHANGE_MESSAGES, handleChange);
}

export default useLibraryChangeSync;
