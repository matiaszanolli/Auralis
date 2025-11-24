import { useState, useEffect, useCallback } from 'react';
import * as playlistService from '../../services/playlistService';
import { useToast } from '../shared/Toast';

interface UseEditPlaylistFormProps {
  playlist: playlistService.Playlist | null;
  onPlaylistUpdated?: () => void;
  onClose: () => void;
}

export const useEditPlaylistForm = ({
  playlist,
  onPlaylistUpdated,
  onClose,
}: UseEditPlaylistFormProps) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const { success, error } = useToast();

  // Update form when playlist changes
  useEffect(() => {
    if (playlist) {
      setName(playlist.name);
      setDescription(playlist.description || '');
    }
  }, [playlist]);

  const handleSave = useCallback(async () => {
    if (!playlist) return;

    if (!name.trim()) {
      error('Please enter a playlist name');
      return;
    }

    setLoading(true);
    try {
      await playlistService.updatePlaylist(playlist.id, {
        name: name.trim(),
        description: description.trim(),
      });

      success(`Playlist "${name}" updated successfully`);

      if (onPlaylistUpdated) {
        onPlaylistUpdated();
      }

      onClose();
    } catch (err) {
      error(`Failed to update playlist: ${err}`);
    } finally {
      setLoading(false);
    }
  }, [playlist, name, description, onPlaylistUpdated, onClose, success, error]);

  const handleClose = useCallback(() => {
    if (!loading) {
      onClose();
    }
  }, [loading, onClose]);

  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && name.trim() && !loading) {
        handleSave();
      }
    },
    [name, loading, handleSave]
  );

  return {
    name,
    setName,
    description,
    setDescription,
    loading,
    handleSave,
    handleClose,
    handleKeyPress,
  };
};
