/**
 * ParameterChip Component
 *
 * Small chip with gradient background for parameter labels.
 * Designed for compact display of parameter values.
 */

import React from 'react';
import { Chip, tokens } from '@/design-system';

interface ParameterChipProps {
  label: string;
  gradient: string;
}

const ParameterChip: React.FC<ParameterChipProps> = React.memo(({ label, gradient }) => {
  return (
    <Chip
      label={label}
      size="small"
      sx={{
        height: tokens.spacing.lg,
        fontSize: tokens.typography.fontSize.xs,
        background: gradient,
        color: tokens.colors.text.primary,
        fontWeight: tokens.typography.fontWeight.semibold,
        borderRadius: tokens.borderRadius.sm,
      }}
    />
  );
});

ParameterChip.displayName = 'ParameterChip';

export default ParameterChip;
