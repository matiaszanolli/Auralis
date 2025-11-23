import { tokens } from '@/design-system/tokens';
import { colorAuroraPrimary } from '../../library/Styles/Color.styles';

/**
 * useSimilarityFormatting - Similarity value and text formatting utilities
 *
 * Handles:
 * - Similarity score level classification
 * - Dimension value formatting
 * - Dimension name formatting
 */
export const useSimilarityFormatting = () => {
  const getSimilarityLevel = (score: number): { label: string; color: string } => {
    if (score >= 0.9) return { label: 'Very Similar', color: tokens.colors.accent.success };
    if (score >= 0.8) return { label: 'Similar', color: colorAuroraPrimary };
    if (score >= 0.7) return { label: 'Somewhat Similar', color: tokens.colors.accent.secondary };
    if (score >= 0.6) return { label: 'Slightly Similar', color: tokens.colors.text.secondary };
    return { label: 'Different', color: tokens.colors.text.disabled };
  };

  const formatDimensionName = (name: string): string => {
    // Convert snake_case to Title Case
    return name
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const formatValue = (value: number, dimension: string): string => {
    // Format based on dimension type
    if (dimension.includes('pct')) {
      return `${value.toFixed(1)}%`;
    } else if (dimension.includes('lufs')) {
      return `${value.toFixed(1)} dB`;
    } else if (dimension.includes('crest') || dimension.includes('db')) {
      return `${value.toFixed(1)} dB`;
    } else if (dimension.includes('tempo')) {
      return `${value.toFixed(0)} BPM`;
    } else if (dimension.includes('ratio') || dimension.includes('correlation')) {
      return value.toFixed(2);
    } else {
      return value.toFixed(2);
    }
  };

  return {
    getSimilarityLevel,
    formatDimensionName,
    formatValue,
  };
};
