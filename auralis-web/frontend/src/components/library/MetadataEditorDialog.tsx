/**
 * MetadataEditorDialog Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Modal dialog for editing track metadata (title, artist, album, etc).
 *
 * Usage:
 * ```typescript
 * <MetadataEditorDialog
 *   track={track}
 *   open={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   onSave={(updates) => handleSaveMetadata(updates)}
 * />
 * ```
 *
 * Props:
 * - track: Track to edit
 * - open: Whether dialog is open
 * - onClose: Callback when dialog closes
 * - onSave: Callback when metadata is saved
 *
 * @module components/library/MetadataEditorDialog
 */

import React, { useState, useCallback, useEffect } from 'react';
import { tokens } from '@/design-system';
import type { Track } from '@/types/domain';

interface MetadataEditorDialogProps {
  track: Track | null;
  open: boolean;
  onClose: () => void;
  onSave: (updates: Partial<Track>) => Promise<void>;
  /** Optional external error message (overrides internal error state) */
  error?: string | null;
  /** Optional external saving state (overrides internal isSaving state) */
  isSaving?: boolean;
}

/**
 * MetadataEditorDialog component
 *
 * Modal dialog for editing track metadata.
 * Shows form with common fields (title, artist, album, year, genre).
 */
export const MetadataEditorDialog: React.FC<MetadataEditorDialogProps> = ({
  track,
  open,
  onClose,
  onSave,
  error: externalError,
  isSaving: externalIsSaving,
}) => {
  const [formData, setFormData] = useState<Partial<Track>>({});
  const [internalIsSaving, setInternalIsSaving] = useState(false);
  const [internalError, setInternalError] = useState<string | null>(null);

  // Use external state if provided, otherwise use internal state
  const isSaving = externalIsSaving ?? internalIsSaving;
  const error = externalError ?? internalError;

  // Initialize form when track changes
  useEffect(() => {
    if (track) {
      setFormData({
        title: track.title,
        artist: track.artist,
        album: track.album,
        year: track.year,
        genre: track.genre,
      });
      setInternalError(null);
    }
  }, [track, open]);

  const handleInputChange = useCallback(
    (field: keyof Track, value: any) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  const handleSave = useCallback(async () => {
    setInternalIsSaving(true);
    setInternalError(null);

    try {
      await onSave(formData);
      onClose();
    } catch (err) {
      setInternalError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setInternalIsSaving(false);
    }
  }, [formData, onSave, onClose]);

  if (!open || !track) return null;

  return (
    <div style={styles.overlay}>
      <div style={styles.dialog}>
        {/* Header */}
        <div style={styles.header}>
          <h2 style={styles.title}>Edit Metadata</h2>
          <button onClick={onClose} style={styles.closeButton} aria-label="Close">
            ✕
          </button>
        </div>

        {/* Form */}
        <div style={styles.form}>
          {/* Title */}
          <div style={styles.field}>
            <label style={styles.label}>Title</label>
            <input
              type="text"
              value={formData.title || ''}
              onChange={(e) => handleInputChange('title', e.target.value)}
              style={styles.input}
            />
          </div>

          {/* Artist */}
          <div style={styles.field}>
            <label style={styles.label}>Artist</label>
            <input
              type="text"
              value={formData.artist || ''}
              onChange={(e) => handleInputChange('artist', e.target.value)}
              style={styles.input}
            />
          </div>

          {/* Album */}
          <div style={styles.field}>
            <label style={styles.label}>Album</label>
            <input
              type="text"
              value={formData.album || ''}
              onChange={(e) => handleInputChange('album', e.target.value)}
              style={styles.input}
            />
          </div>

          {/* Year */}
          <div style={styles.field}>
            <label style={styles.label}>Year</label>
            <input
              type="number"
              value={formData.year || ''}
              onChange={(e) => handleInputChange('year', parseInt(e.target.value))}
              style={styles.input}
            />
          </div>

          {/* Genre */}
          <div style={styles.field}>
            <label style={styles.label}>Genre</label>
            <input
              type="text"
              value={formData.genre || ''}
              onChange={(e) => handleInputChange('genre', e.target.value)}
              style={styles.input}
            />
          </div>

          {/* Error message */}
          {error && <div style={styles.error}>{error}</div>}
        </div>

        {/* Footer */}
        <div style={styles.footer}>
          <button onClick={onClose} style={styles.cancelButton} disabled={isSaving}>
            Cancel
          </button>
          <button onClick={handleSave} style={styles.saveButton} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
};

const styles = {
  overlay: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    zIndex: 1000,
  },

  dialog: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '90%',
    maxWidth: '500px',
    backgroundColor: tokens.colors.bg.primary,
    borderRadius: tokens.borderRadius.lg,
    boxShadow: tokens.shadows.xl,
  },

  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  closeButton: {
    width: '32px',
    height: '32px',
    padding: 0,
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
    color: tokens.colors.text.secondary,
    fontSize: '20px',
  },

  form: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    overflow: 'auto',
    maxHeight: '400px',
  },

  field: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  label: {
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    color: tokens.colors.text.primary,
  },

  input: {
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.md,
  },

  error: {
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.semantic.error,
    color: tokens.colors.text.primary,
    borderRadius: tokens.borderRadius.md,
    fontSize: tokens.typography.fontSize.sm,
  },

  footer: {
    display: 'flex',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    borderTop: `1px solid ${tokens.colors.border.light}`,
  },

  cancelButton: {
    flex: 1,
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
  },

  saveButton: {
    flex: 1,
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.accent.primary,
    border: 'none',
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
  },
};

export default MetadataEditorDialog;
