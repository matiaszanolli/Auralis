/**
 * EnhancementPane Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Main enhancement settings panel.
 * Combines PresetSelector, IntensitySlider, MasteringRecommendation, and ParameterBar.
 *
 * @module components/enhancement/EnhancementPane
 */

import React from 'react';
import { tokens } from '@/design-system';
import { useEnhancementToggle } from '@/hooks/enhancement/useEnhancementControl';
import PresetSelector from './PresetSelector';
import IntensitySlider from './IntensitySlider';
import MasteringRecommendation from './MasteringRecommendation';
import ParameterBar from './ParameterBar';

export const EnhancementPane: React.FC = () => {
  const { enabled, toggleEnabled } = useEnhancementToggle();

  return (
    <div style={styles.container}>
      {/* Header with toggle */}
      <div style={styles.header}>
        <h1 style={styles.title}>Audio Enhancement</h1>
        <button
          onClick={toggleEnabled}
          style={{
            ...styles.toggleButton,
            ...(enabled && styles.toggleButtonActive),
          }}
        >
          {enabled ? 'Enabled' : 'Disabled'}
        </button>
      </div>

      {enabled && (
        <div style={styles.content}>
          <PresetSelector />
          <IntensitySlider />
          <MasteringRecommendation />
          <ParameterBar />
        </div>
      )}

      {!enabled && (
        <div style={styles.disabledMessage}>
          <p>Enhancement is currently disabled</p>
          <p style={styles.disabledSubtext}>Click the toggle above to enable</p>
        </div>
      )}
    </div>
  );
};

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.lg,
    padding: tokens.spacing.lg,
    backgroundColor: tokens.colors.bg.primary,
  },

  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.xl,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  toggleButton: {
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: tokens.colors.bg.secondary,
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontWeight: tokens.typography.fontWeight.bold,
  },

  toggleButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    borderColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primary,
  },

  content: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.lg,
  },

  disabledMessage: {
    padding: tokens.spacing.lg,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
    textAlign: 'center' as const,
    color: tokens.colors.text.secondary,
  },

  disabledSubtext: {
    margin: `${tokens.spacing.sm} 0 0 0`,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
  },
};

export default EnhancementPane;
