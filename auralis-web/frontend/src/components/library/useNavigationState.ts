import { useState, useEffect, useCallback } from 'react';

/**
 * `playlist-<id>` view ids come from the sidebar's PlaylistList (#6007).
 * Returns the numeric id, or null for any other view — including malformed
 * playlist ids (`playlist-`, `playlist-abc`), which fall through to the
 * honest Songs config like every other unknown view (#5620).
 */
export function parsePlaylistViewId(view: string): number | null {
  if (!view.startsWith('playlist-')) return null;
  const id = parseInt(view.slice('playlist-'.length), 10);
  return Number.isInteger(id) && id > 0 ? id : null;
}

interface UseNavigationStateProps {
  view: string;
}

export const useNavigationState = ({ view }: UseNavigationStateProps) => {
  const [selectedAlbumId, setSelectedAlbumId] = useState<number | null>(null);
  const [selectedArtistId, setSelectedArtistId] = useState<number | null>(null);
  const [selectedArtistName, setSelectedArtistName] = useState<string>('');

  // Reset navigation state when view changes
  useEffect(() => {
    setSelectedAlbumId(null);
    setSelectedArtistId(null);
    setSelectedArtistName('');
  }, [view]);

  const handleBackFromAlbum = useCallback(() => {
    setSelectedAlbumId(null);
    // If we came from artist view, stay in artist detail
    // (selectedArtistId will still be set)
  }, []);

  const handleBackFromArtist = useCallback(() => {
    setSelectedArtistId(null);
    setSelectedArtistName('');
  }, []);

  const handleAlbumClick = useCallback((id: number) => {
    setSelectedAlbumId(id);
  }, []);

  const handleArtistClick = useCallback((id: number, name: string) => {
    setSelectedArtistId(id);
    setSelectedArtistName(name);
  }, []);

  return {
    selectedAlbumId,
    selectedArtistId,
    selectedArtistName,
    handleBackFromAlbum,
    handleBackFromArtist,
    handleAlbumClick,
    handleArtistClick,
  };
};
