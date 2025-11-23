import { useCallback } from 'react';
import { tokens } from '@/design-system/tokens';

export const useSimilarTracksFormatting = () => {
  const getSimilarityColor = useCallback((score: number): string => {
    if (score >= 0.9) return tokens.colors.accent.success; // Very similar (90%+) - turquoise
    if (score >= 0.8) return tokens.colors.accent.purple; // Similar (80-90%) - purple
    if (score >= 0.7) return tokens.colors.accent.secondary; // Somewhat similar (70-80%) - secondary
    return tokens.colors.text.secondary; // Less similar (<70%) - gray
  }, []);

  const formatDuration = useCallback((seconds?: number): string => {
    if (!seconds) return '';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }, []);

  return { getSimilarityColor, formatDuration };
};
