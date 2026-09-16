import { useState, useCallback } from 'react';
import { useToast } from '@/components/shared/Toast';

export const useMetadataEditing = (onFetchTracks: () => Promise<void>) => {
  const [editMetadataDialogOpen, setEditMetadataDialogOpen] = useState(false);
  // editingTrackId is kept after close (#5397): CozyLibraryView mounts the
  // dialog while it is non-null, so clearing it together with `open` unmounted
  // the dialog before MUI's exit transition could run. editSession keys the
  // dialog so every open still starts from a freshly loaded form.
  const [editingTrackId, setEditingTrackId] = useState<number | null>(null);
  const [editSession, setEditSession] = useState(0);
  const { success } = useToast();

  const handleEditMetadata = useCallback((trackId: number) => {
    setEditingTrackId(trackId);
    setEditSession((n) => n + 1);
    setEditMetadataDialogOpen(true);
  }, []);

  const handleCloseEditDialog = useCallback(() => {
    setEditMetadataDialogOpen(false);
  }, []);

  const handleSaveMetadata = useCallback(async () => {
    success('Metadata updated successfully');
    await onFetchTracks();
  }, [onFetchTracks, success]);

  return {
    editMetadataDialogOpen,
    editingTrackId,
    editSession,
    handleEditMetadata,
    handleCloseEditDialog,
    handleSaveMetadata,
  };
};
