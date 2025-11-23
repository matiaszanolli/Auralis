/**
 * useParameterFormatting Hook
 *
 * Provides formatting utilities for processing parameters.
 * Handles number formatting, threshold checking, and value validation.
 */

import { tokens } from '../../design-system/tokens';

interface ProcessingParams {
  target_lufs: number;
  peak_target_db: number;
  bass_boost: number;
  air_boost: number;
  compression_amount: number;
  expansion_amount: number;
  stereo_width: number;
}

interface FormattedParameter {
  label: string;
  value: string;
  shouldShow: boolean;
  valueColor?: string;
}

export const useParameterFormatting = (params: ProcessingParams) => {
  // Format number to fixed decimal places
  const formatNumber = (value: number | undefined, decimals: number = 1): string => {
    if (value === undefined || value === null) return '—';
    return value.toFixed(decimals);
  };

  // Format percentage value
  const formatPercent = (value: number | undefined): string => {
    if (value === undefined || value === null) return '—';
    return `${Math.round(value * 100)}%`;
  };

  // Check if value should be displayed (above threshold)
  const shouldShowValue = (value: number | undefined, threshold: number = 0.1): boolean => {
    if (value === undefined || value === null) return false;
    return Math.abs(value) > threshold;
  };

  // Format decibel value with sign
  const formatDecibel = (value: number | undefined, decimals: number = 1): string => {
    const formatted = formatNumber(value, decimals);
    if (formatted === '—') return formatted;
    const num = parseFloat(formatted);
    return num > 0 ? `+${formatted}` : formatted;
  };

  // Get color for adjustment value (positive = success, negative = warning)
  const getAdjustmentColor = (value: number | undefined): string => {
    if (value === undefined || value === null) return tokens.colors.text.primary;
    return value > 0 ? tokens.colors.accent.success : tokens.colors.accent.warning;
  };

  // Format all parameters
  const formatTargetLoudness = (): FormattedParameter => ({
    label: 'Target Loudness',
    value: `${formatNumber(params.target_lufs)} LUFS`,
    shouldShow: true,
  });

  const formatPeakTarget = (): FormattedParameter => ({
    label: 'Peak Level',
    value: `${formatNumber(params.peak_target_db)} dB`,
    shouldShow: true,
  });

  const formatBassBoost = (): FormattedParameter => ({
    label: 'Bass Adjustment',
    value: `${formatDecibel(params.bass_boost)} dB`,
    valueColor: getAdjustmentColor(params.bass_boost),
    shouldShow: shouldShowValue(params.bass_boost),
  });

  const formatAirBoost = (): FormattedParameter => ({
    label: 'Air Adjustment',
    value: `${formatDecibel(params.air_boost)} dB`,
    valueColor: getAdjustmentColor(params.air_boost),
    shouldShow: shouldShowValue(params.air_boost),
  });

  const formatCompression = (): FormattedParameter => ({
    label: 'Compression',
    value: formatPercent(params.compression_amount),
    shouldShow: shouldShowValue(params.compression_amount, 0.05),
  });

  const formatExpansion = (): FormattedParameter => ({
    label: 'Expansion',
    value: formatPercent(params.expansion_amount),
    valueColor: tokens.colors.accent.info,
    shouldShow: shouldShowValue(params.expansion_amount, 0.05),
  });

  const formatStereoWidth = (): FormattedParameter => ({
    label: 'Stereo Width',
    value: params.stereo_width !== undefined && params.stereo_width !== null ? `${Math.round(params.stereo_width * 100)}%` : '—%',
    shouldShow: true,
  });

  return {
    formatNumber,
    formatPercent,
    formatDecibel,
    formatTargetLoudness,
    formatPeakTarget,
    formatBassBoost,
    formatAirBoost,
    formatCompression,
    formatExpansion,
    formatStereoWidth,
  };
};
