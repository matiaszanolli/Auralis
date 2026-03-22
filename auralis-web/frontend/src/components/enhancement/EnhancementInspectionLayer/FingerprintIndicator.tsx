import React from 'react';
import { keyframes } from '@mui/material';
import { tokens } from '@/design-system';

const spin = keyframes`
  to { transform: rotate(360deg); }
`;

interface FingerprintIndicatorProps {
  fingerprintStatus: 'idle' | 'analyzing' | 'complete' | 'error' | 'failed';
  fingerprintMessage?: string | null;
}

export const FingerprintIndicator = ({
  fingerprintStatus,
  fingerprintMessage,
}: FingerprintIndicatorProps) => {
  if (fingerprintStatus === 'idle') return null;

  return (
    <div
      style={{
        ...styles.fingerprintIndicator,
        backgroundColor:
          fingerprintStatus === 'analyzing'
            ? tokens.colors.semantic.warning + '15'
            : fingerprintStatus === 'complete'
              ? tokens.colors.semantic.success + '15'
              : fingerprintStatus === 'error' || fingerprintStatus === 'failed'
                ? tokens.colors.semantic.error + '15'
                : 'transparent',
        borderColor:
          fingerprintStatus === 'analyzing'
            ? tokens.colors.semantic.warning
            : fingerprintStatus === 'complete'
              ? tokens.colors.semantic.success
              : tokens.colors.semantic.error,
      }}
    >
      <div style={styles.fingerprintContent}>
        {fingerprintStatus === 'analyzing' && (
          <>
            <div style={styles.spinner} />
            <span style={styles.fingerprintText}>Analyzing audio for optimal mastering...</span>
          </>
        )}
        {fingerprintStatus === 'complete' && (
          <>
            <span style={{ fontSize: tokens.typography.fontSize.md }}>&#x2705;</span>
            <span style={styles.fingerprintText}>Audio analysis complete</span>
          </>
        )}
        {(fingerprintStatus === 'error' || fingerprintStatus === 'failed') && (
          <>
            <span style={{ fontSize: tokens.typography.fontSize.md }}>&#x26A0;&#xFE0F;</span>
            <span style={{ ...styles.fingerprintText, color: tokens.colors.semantic.error }}>
              {fingerprintMessage || 'Audio analysis failed'}
            </span>
          </>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  fingerprintIndicator: {
    padding: tokens.spacing.md,
    borderRadius: tokens.borderRadius.sm,
    border: `1px solid`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '44px',
  },

  fingerprintContent: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
  },

  spinner: {
    width: '16px',
    height: '16px',
    border: `2px solid ${tokens.colors.semantic.warning}40`,
    borderTopColor: tokens.colors.semantic.warning,
    borderRadius: tokens.borderRadius.full,
    animation: `${spin} 1s linear infinite`,
  },

  fingerprintText: {
    fontSize: tokens.typography.fontSize.base,
    fontWeight: tokens.typography.fontWeight.medium,
    color: tokens.colors.text.primary,
  },
};
