/**
 * ParameterBar Component
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Container for displaying multiple audio processing parameters.
 *
 * @module components/enhancement/ParameterBar
 */

import React from 'react';
import { tokens } from '@/design-system';
import ParameterDisplay from './ParameterDisplay';

export const ParameterBar: React.FC = () => {
  return (
    <div style={styles.container}>
      <h3 style={styles.title}>Processing Parameters</h3>
      <div style={styles.grid}>
        <ParameterDisplay label="Loudness" value={-14.5} unit="LUFS" />
        <ParameterDisplay label="Dynamics" value={6.2} unit="dB" />
        <ParameterDisplay label="Clarity" value={45} unit="%" />
        <ParameterDisplay label="Presence" value={65} unit="%" />
      </div>
    </div>
  );
};

const styles = {
  container: {
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
  },
  title: {
    margin: `0 0 ${tokens.spacing.md} 0`,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: tokens.spacing.md,
  },
};

export default ParameterBar;
