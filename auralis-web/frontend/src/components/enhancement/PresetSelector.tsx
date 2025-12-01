/**
 * PresetSelector Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Selects audio enhancement preset (adaptive, gentle, warm, bright, punchy).
 * Shows preset descriptions and handles selection.
 *
 * Usage:
 * ```typescript
 * <PresetSelector />
 * ```
 *
 * @module components/enhancement/PresetSelector
 */

import React, { useCallback } from 'react';
import { tokens } from '@/design-system/tokens';
import { usePresetControl } from '@/hooks/enhancement/useEnhancementControl';
import { ENHANCEMENT_PRESET_DESCRIPTIONS } from '@/types/domain';
import type { EnhancementPreset } from '@/types/domain';

const PRESETS: EnhancementPreset[] = ['adaptive', 'gentle', 'warm', 'bright', 'punchy'];

/**
 * PresetSelector component
 *
 * Grid of preset buttons with descriptions.
 * Shows currently selected preset with visual feedback.
 * Loading and error states included.
 */
export const PresetSelector: React.FC = () => {
  const { preset, setPreset, isLoading, error } = usePresetControl();

  const handlePresetClick = useCallback(
    async (newPreset: EnhancementPreset) => {
      try {
        await setPreset(newPreset);
      } catch (err) {
        console.error('Failed to change preset:', err);
      }
    },
    [setPreset]
  );

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Enhancement Preset</h2>

      {error && <div style={styles.error}>{error.message}</div>}

      <div style={styles.grid}>
        {PRESETS.map((p) => (
          <button
            key={p}
            onClick={() => handlePresetClick(p)}
            disabled={isLoading}
            style={{
              ...styles.presetButton,
              ...(preset === p && styles.presetButtonActive),
            }}
          >
            <div style={styles.presetName}>{p}</div>
            <div style={styles.presetDesc}>
              {ENHANCEMENT_PRESET_DESCRIPTIONS[p]}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
    gap: tokens.spacing.md,
  },

  presetButton: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.primary,
    border: `1px solid ${tokens.colors.border.medium}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    textAlign: 'center' as const,

    '&:hover': {
      borderColor: tokens.colors.accent.primary,
      boxShadow: tokens.shadows.md,
    },
  },

  presetButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    borderColor: tokens.colors.accent.primary,
    color: tokens.colors.text.secondary,
  },

  presetName: {
    fontWeight: tokens.typography.fontWeight.bold,
    fontSize: tokens.typography.fontSize.md,
    textTransform: 'capitalize' as const,
  },

  presetDesc: {
    fontSize: tokens.typography.fontSize.xs,
    opacity: 0.8,
  },

  error: {
    color: tokens.colors.accent.error,
    fontSize: tokens.typography.fontSize.sm,
  },
};

export default PresetSelector;
