import { useMemo } from 'react';
import { getArtistContextActions } from '../../shared/ContextMenu';
import { useToast } from '../../shared/ui/feedback';

interface ArtistInfo {
  id: number;
  name: string;
  album_count: number;
  track_count: number;
}

interface UseContextMenuActionsProps {
  artist: ArtistInfo | null;
  onArtistClick?: (artistId: number, artistName: string) => void;
}

/**
 * useContextMenuActions - Generates context menu actions for artist
 *
 * Creates artist actions with toast notifications and callbacks.
 * Memoized to prevent unnecessary re-renders.
 */
export const useContextMenuActions = ({
  artist,
  onArtistClick,
}: UseContextMenuActionsProps) => {
  const { success, info } = useToast();

  return useMemo(() => {
    if (!artist) return [];

    return getArtistContextActions(artist.id, {
      onPlayAll: () => {
        success(`Playing all songs by ${artist.name}`);
        // TODO: Implement play all artist tracks
      },
      onAddToQueue: () => {
        success(`Added ${artist.name} to queue`);
        // TODO: Implement add artist to queue
      },
      onShowAlbums: () => {
        info(`Showing albums by ${artist.name}`);
        if (onArtistClick) {
          onArtistClick(artist.id, artist.name);
        }
      },
      onShowInfo: () => {
        info(
          `Artist: ${artist.name}\n${artist.album_count} albums • ${artist.track_count} tracks`
        );
        // TODO: Show artist info modal
      },
    });
  }, [artist, onArtistClick, success, info]);
};
