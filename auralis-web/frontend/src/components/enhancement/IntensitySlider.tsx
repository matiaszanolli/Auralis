/**
 * IntensitySlider Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Slider for adjusting enhancement intensity (0.0-1.0).
 * Shows percentage and real-time feedback.
 *
 * Usage:
 * ```typescript
 * <IntensitySlider />
 * ```
 *
 * @module components/enhancement/IntensitySlider
 */

import React, { useCallback, useState } from 'react';
import { tokens } from '@/design-system/tokens';
import { useIntensityControl } from '@/hooks/enhancement/useEnhancementControl';

/**
 * IntensitySlider component
 *
 * Slider for adjusting enhancement intensity with real-time feedback.
 * Shows percentage, intensity labels (subtle, moderate, strong).
 */
export const IntensitySlider: React.FC = () => {
  const { intensity, setIntensity, isLoading } = useIntensityControl();
  const [isDragging, setIsDragging] = useState(false);
  const [dragValue, setDragValue] = useState(intensity);

  const handleSliderChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = parseFloat(e.target.value);
    setDragValue(newValue);
    setIsDragging(true);
  }, []);

  const handleSliderRelease = useCallback(async () => {
    setIsDragging(false);
    try {
      await setIntensity(dragValue);
    } catch (err) {
      console.error('Failed to set intensity:', err);
      setDragValue(intensity);
    }
  }, [dragValue, intensity, setIntensity]);

  const displayIntensity = isDragging ? dragValue : intensity;
  const percentage = Math.round(displayIntensity * 100);

  const getIntensityLabel = (value: number): string => {
    if (value < 0.33) return 'Subtle';
    if (value < 0.66) return 'Moderate';
    return 'Strong';
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h3 style={styles.title}>Intensity</h3>
        <div style={styles.percentage}>{percentage}%</div>
      </div>

      <div style={styles.sliderContainer}>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={displayIntensity}
          onChange={handleSliderChange}
          onMouseUp={handleSliderRelease}
          onTouchEnd={handleSliderRelease}
          disabled={isLoading}
          style={{
            ...styles.slider,
            background: `linear-gradient(to right, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.primary} ${percentage}%, ${tokens.colors.bg.tertiary} ${percentage}%, ${tokens.colors.bg.tertiary} 100%)`,
          }}
          aria-label="Intensity"
        />
      </div>

      <div style={styles.footer}>
        <div style={styles.label}>Subtle</div>
        <div style={styles.label}>{getIntensityLabel(displayIntensity)}</div>
        <div style={styles.label}>Strong</div>
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

  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  percentage: {
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.accent.primary,
    minWidth: '50px',
    textAlign: 'right' as const,
  },

  sliderContainer: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
  },

  slider: {
    width: '100%',
    height: '6px',
    cursor: 'pointer',
    appearance: 'none' as const,
    WebkitAppearance: 'none' as const,
    borderRadius: tokens.borderRadius.full,
    border: 'none',
    outline: 'none',
  },

  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.tertiary,
  },

  label: {
    flex: 1,
    textAlign: 'center' as const,
  },
};

export default IntensitySlider;
