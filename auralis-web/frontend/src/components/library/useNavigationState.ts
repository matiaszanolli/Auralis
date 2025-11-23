import { useState, useEffect, useCallback } from 'react';

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
