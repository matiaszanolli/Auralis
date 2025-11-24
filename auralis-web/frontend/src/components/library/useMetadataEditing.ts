import { useState, useCallback } from 'react';
import { useToast } from '../shared/Toast';

export const useMetadataEditing = (onFetchTracks: () => Promise<void>) => {
  const [editMetadataDialogOpen, setEditMetadataDialogOpen] = useState(false);
  const [editingTrackId, setEditingTrackId] = useState<number | null>(null);
  const { success } = useToast();

  const handleEditMetadata = useCallback((trackId: number) => {
    setEditingTrackId(trackId);
    setEditMetadataDialogOpen(true);
  }, []);

  const handleCloseEditDialog = useCallback(() => {
    setEditMetadataDialogOpen(false);
    setEditingTrackId(null);
  }, []);

  const handleSaveMetadata = useCallback(async () => {
    success('Metadata updated successfully');
    await onFetchTracks();
  }, [onFetchTracks, success]);

  return {
    editMetadataDialogOpen,
    editingTrackId,
    handleEditMetadata,
    handleCloseEditDialog,
    handleSaveMetadata,
  };
};
