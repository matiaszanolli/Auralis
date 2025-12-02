/**
 * useMetadataForm Hook
 *
 * Manages metadata form state and operations:
 * - Fetch metadata from API
 * - Update metadata fields
 * - Save metadata with validation
 * - Handle loading/error/success states
 */

import { useState, useEffect } from 'react';

export interface MetadataFields {
  title?: string;
  artist?: string;
  album?: string;
  albumartist?: string;
  year?: number | string;
  genre?: string;
  track?: number | string;
  disc?: number | string;
  comment?: string;
  bpm?: number | string;
  composer?: string;
  publisher?: string;
}

export const useMetadataForm = (
  trackId: number,
  initialMetadata?: MetadataFields,
  onSave?: (trackId: number, metadata: MetadataFields) => void
) => {
  const [metadata, setMetadata] = useState<MetadataFields>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Load current metadata
  useEffect(() => {
    if (trackId) {
      if (initialMetadata) {
        setMetadata(initialMetadata);
      } else {
        fetchMetadata();
      }
    }
  }, [trackId, initialMetadata]);

  const fetchMetadata = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/metadata/tracks/${trackId}`);

      if (!response.ok) {
        throw new Error('Failed to fetch metadata');
      }

      const data = await response.json();
      setMetadata(data.metadata || {});
    } catch (err) {
      console.error('Error fetching metadata:', err);
      setError(err instanceof Error ? err.message : 'Failed to load metadata');
    } finally {
      setLoading(false);
    }
  };

  const updateField = (field: keyof MetadataFields, value: string) => {
    setMetadata((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const saveMetadata = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      // Filter out empty values and convert numbers
      const updates: Partial<MetadataFields> = {};
      Object.entries(metadata).forEach(([key, value]) => {
        if (value !== undefined && value !== '') {
          // Convert numeric fields
          if (['year', 'track', 'disc', 'bpm'].includes(key)) {
            const num = parseInt(String(value), 10);
            if (!isNaN(num)) {
              (updates as Record<string, any>)[key] = num;
            }
          } else {
            (updates as Record<string, any>)[key] = value;
          }
        }
      });

      if (Object.keys(updates).length === 0) {
        setError('No changes to save');
        setSaving(false);
        return;
      }

      const response = await fetch(`/api/metadata/tracks/${trackId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save metadata');
      }

      setSuccess(true);

      // Call onSave callback if provided
      if (onSave) {
        onSave(trackId, updates);
      }

      return true;
    } catch (err) {
      console.error('Error saving metadata:', err);
      setError(err instanceof Error ? err.message : 'Failed to save metadata');
      return false;
    } finally {
      setSaving(false);
    }
  };

  return {
    metadata,
    loading,
    saving,
    error,
    success,
    updateField,
    saveMetadata,
    setSuccess,
    setError,
  };
};
