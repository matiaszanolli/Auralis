/**
 * useMetadataForm Hook
 *
 * Manages metadata form state and operations:
 * - Fetch metadata from API
 * - Update metadata fields
 * - Save metadata with validation
 * - Handle loading/error/success states
 */

import { useState, useEffect, useRef } from 'react';

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

  // #4175: cancel an in-flight PUT on unmount so saveMetadata never runs
  // setSuccess/setSaving/setError on a dead hook (and a reopened dialog can't
  // race a stale save). Mirrors the GET path's controller (#3601).
  const saveAbortRef = useRef<AbortController | null>(null);
  useEffect(() => () => saveAbortRef.current?.abort(), []);

  // #3601: AbortController on metadata fetch so unmount cancels the request
  // and we don't setState on a dead component. Also #3643: shape-guard the
  // response and surface an error instead of silently populating empty form
  // fields when the payload doesn't match { metadata: {...} }.
  useEffect(() => {
    if (!trackId) return;
    if (initialMetadata) {
      setMetadata(initialMetadata);
      return;
    }

    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/metadata/tracks/${trackId}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error('Failed to fetch metadata');

        const data: unknown = await response.json();
        if (controller.signal.aborted) return;

        if (
          !data ||
          typeof data !== 'object' ||
          !('metadata' in data) ||
          typeof (data as { metadata: unknown }).metadata !== 'object'
        ) {
          throw new Error('Invalid metadata response from server');
        }
        setMetadata((data as { metadata: MetadataFields }).metadata || {});
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('Error fetching metadata:', err);
        setError(err instanceof Error ? err.message : 'Failed to load metadata');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    run();
    return () => controller.abort();
  }, [trackId, initialMetadata]);

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

    // Abort any prior in-flight save and track this one so unmount cancels it.
    saveAbortRef.current?.abort();
    const controller = new AbortController();
    saveAbortRef.current = controller;

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
        signal: controller.signal,
      });

      // Bail before any setState if the dialog closed mid-request.
      if (controller.signal.aborted) return false;

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save metadata');
      }

      if (controller.signal.aborted) return false;
      setSuccess(true);

      // Call onSave callback if provided
      if (onSave) {
        onSave(trackId, updates);
      }

      return true;
    } catch (err) {
      // Aborted by unmount — not user-facing.
      if ((err as Error).name === 'AbortError') return false;
      console.error('Error saving metadata:', err);
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : 'Failed to save metadata');
      }
      return false;
    } finally {
      if (!controller.signal.aborted) setSaving(false);
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
