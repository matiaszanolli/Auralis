import { useState, useCallback } from 'react';

interface UsePresetSelectionReturn {
  hoveredPreset: string | null;
  setHoveredPreset: (preset: string | null) => void;
  getCirclePosition: (angle: number, radius: number) => { x: number; y: number };
}

/**
 * Hook for managing preset selection state and hover feedback in RadialPresetSelector
 *
 * Handles:
 * - Hover state for visual feedback (scale, shadow changes)
 * - Position calculations for circular layout
 * - Memoized callback for hover changes
 */
export const usePresetSelection = (): UsePresetSelectionReturn => {
  const [hoveredPreset, setHoveredPreset] = useState<string | null>(null);

  /**
   * Calculate position on circle based on angle and radius
   * @param angle - Angle in degrees (0-360)
   * @param radius - Distance from center
   * @returns x, y coordinates relative to center
   */
  const getCirclePosition = useCallback((angle: number, radius: number) => {
    const rad = ((angle - 90) * Math.PI) / 180; // -90 to start from top
    return {
      x: Math.cos(rad) * radius,
      y: Math.sin(rad) * radius,
    };
  }, []);

  return {
    hoveredPreset,
    setHoveredPreset,
    getCirclePosition,
  };
};

export default usePresetSelection;
