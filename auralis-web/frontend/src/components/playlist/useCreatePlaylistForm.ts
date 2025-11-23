import { useState, useCallback } from 'react';
import * as playlistService from '../../services/playlistService';
import { useToast } from '../shared/ui/feedback';

interface UseCreatePlaylistFormProps {
  initialTrackIds?: number[];
  onPlaylistCreated?: (playlist: playlistService.Playlist) => void;
  onClose: () => void;
}

export const useCreatePlaylistForm = ({
  initialTrackIds,
  onPlaylistCreated,
  onClose,
}: UseCreatePlaylistFormProps) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const { success, error } = useToast();

  const handleCreate = useCallback(async () => {
    if (!name.trim()) {
      error('Please enter a playlist name');
      return;
    }

    setLoading(true);
    try {
      const playlist = await playlistService.createPlaylist({
        name: name.trim(),
        description: description.trim(),
        track_ids: initialTrackIds,
      });

      success(`Playlist "${name}" created successfully`);

      if (onPlaylistCreated) {
        onPlaylistCreated(playlist);
      }

      // Reset form
      setName('');
      setDescription('');
      onClose();
    } catch (err) {
      error(`Failed to create playlist: ${err}`);
    } finally {
      setLoading(false);
    }
  }, [name, description, initialTrackIds, onPlaylistCreated, onClose, success, error]);

  const handleClose = useCallback(() => {
    if (!loading) {
      setName('');
      setDescription('');
      onClose();
    }
  }, [loading, onClose]);

  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && name.trim() && !loading) {
        handleCreate();
      }
    },
    [name, loading, handleCreate]
  );

  return {
    name,
    setName,
    description,
    setDescription,
    loading,
    handleCreate,
    handleClose,
    handleKeyPress,
  };
};
