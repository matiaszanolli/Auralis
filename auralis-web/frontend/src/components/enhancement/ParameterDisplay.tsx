/**
 * ParameterDisplay Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Shows audio processing parameter values (loudness, dynamics, EQ, etc).
 *
 * @module components/enhancement/ParameterDisplay
 */

import React from 'react';
import { tokens } from '@/design-system/tokens';

interface ParameterDisplayProps {
  label: string;
  value: number;
  unit?: string;
  min?: number;
  max?: number;
}

export const ParameterDisplay: React.FC<ParameterDisplayProps> = ({
  label,
  value,
  unit,
  min = 0,
  max = 100,
}) => {
  const percentage = ((value - min) / (max - min)) * 100;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.label}>{label}</span>
        <span style={styles.value}>
          {value.toFixed(1)}
          {unit && ` ${unit}`}
        </span>
      </div>
      <div style={styles.bar}>
        <div
          style={{
            ...styles.fill,
            width: `${percentage}%`,
          }}
        />
      </div>
    </div>
  );
};

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: tokens.typography.fontSize.sm,
  },
  label: { color: tokens.colors.text.secondary },
  value: { color: tokens.colors.accent.primary, fontWeight: tokens.typography.fontWeight.bold },
  bar: {
    width: '100%',
    height: '6px',
    backgroundColor: tokens.colors.bg.tertiary,
    borderRadius: tokens.borderRadius.full,
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    backgroundColor: tokens.colors.accent.primary,
    transition: 'width 0.3s ease',
  },
};

export default ParameterDisplay;
