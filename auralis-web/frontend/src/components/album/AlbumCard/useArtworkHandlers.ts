/**
 * useArtworkHandlers Hook
 *
 * Manages artwork operations for album cards:
 * - Download artwork from online sources
 * - Extract artwork from audio files
 * - Delete existing artwork
 * - Loading state tracking
 */

import { useState } from 'react';
import { downloadArtwork, extractArtwork, deleteArtwork } from '../../../services/artworkService';
import { useToast } from '../../shared/Toast';

export const useArtworkHandlers = (albumId: number, onArtworkUpdated?: () => void) => {
  const [downloading, setDownloading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const { success, error: showError } = useToast();

  const handleDownloadArtwork = async () => {
    setDownloading(true);

    try {
      const result = await downloadArtwork(albumId);
      success(`Downloaded artwork for "${result.album}" by ${result.artist}`);
      onArtworkUpdated?.();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to download artwork');
    } finally {
      setDownloading(false);
    }
  };

  const handleExtractArtwork = async () => {
    setExtracting(true);

    try {
      await extractArtwork(albumId);
      success(`Extracted artwork from audio files`);
      onArtworkUpdated?.();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to extract artwork');
    } finally {
      setExtracting(false);
    }
  };

  const handleDeleteArtwork = async () => {
    try {
      await deleteArtwork(albumId);
      success('Artwork deleted');
      onArtworkUpdated?.();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to delete artwork');
    }
  };

  return {
    downloading,
    extracting,
    handleDownloadArtwork,
    handleExtractArtwork,
    handleDeleteArtwork,
  };
};
