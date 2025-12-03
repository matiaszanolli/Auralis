/**
 * Processing Toast - Subtle, non-intrusive processing status indicator
 *
 * Shows real-time processing stats in a compact bottom-right toast
 * that doesn't block the UI or interrupt the user experience.
 */

import React from 'react';
import { Box, Paper, Typography, Fade, Stack } from '@mui/material';
import { AutoAwesome } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { ProcessingStatsChips } from './ProcessingStatsChips';

interface ProcessingStats {
  status: 'analyzing' | 'processing' | 'idle';
  progress?: number; // 0-100
  currentChunk?: number;
  totalChunks?: number;
  processingSpeed?: number; // real-time factor (e.g., 8x)
  cacheHit?: boolean;
}

interface ProcessingToastProps {
  stats: ProcessingStats;
  show: boolean;
}

export const ProcessingToast: React.FC<ProcessingToastProps> = ({ stats, show }) => {
  if (!show || stats.status === 'idle') {
    return null;
  }

  const getStatusText = () => {
    if (stats.status === 'analyzing') {
      return stats.cacheHit ? 'Loading fingerprint...' : 'Analyzing audio...';
    }
    if (stats.currentChunk !== undefined && stats.totalChunks !== undefined) {
      return `Processing chunk ${stats.currentChunk}/${stats.totalChunks}`;
    }
    return 'Processing...';
  };

  const getStatusColor = () => {
    if (stats.cacheHit) return tokens.colors.semantic.success;
    if (stats.status === 'analyzing') return tokens.colors.accent.primary;
    return tokens.colors.accent.primary;
  };

  return (
    <Fade in={show}>
      <Paper
        elevation={8}
        sx={{
          position: 'fixed',
          bottom: `calc(${tokens.components.playerBar.height} + ${tokens.spacing.sm})`,
          right: tokens.spacing.lg,
          width: '280px',
          backgroundColor: tokens.components.playerBar.background,
          backdropFilter: 'blur(20px)',
          borderRadius: tokens.borderRadius.lg,
          border: `1px solid ${tokens.colors.border.light}`,
          overflow: 'hidden',
          zIndex: tokens.zIndex.toast,
          boxShadow: tokens.shadows.xl
        }}
      >
        <Box sx={{ p: tokens.spacing.md }}>
          {/* Header with icon */}
          <Stack direction="row" spacing={tokens.spacing.sm} alignItems="center" sx={{ mb: tokens.spacing.sm }}>
            <AutoAwesome
              sx={{
                fontSize: tokens.typography.fontSize.lg,
                color: getStatusColor(),
                animation: stats.status === 'analyzing' ? 'pulse 2s ease-in-out infinite' : 'none',
                '@keyframes pulse': {
                  '0%, 100%': { opacity: 1 },
                  '50%': { opacity: 0.5 }
                }
              }}
            />
            <Typography
              variant="body2"
              sx={{
                color: tokens.colors.text.primary,
                fontWeight: tokens.typography.fontWeight.semibold,
                fontSize: tokens.typography.fontSize.sm
              }}
            >
              {getStatusText()}
            </Typography>
          </Stack>

          {/* Stats chips */}
          <ProcessingStatsChips
            cacheHit={stats.cacheHit}
            processingSpeed={stats.processingSpeed}
            currentChunk={stats.currentChunk}
            totalChunks={stats.totalChunks}
          />
        </Box>
      </Paper>
    </Fade>
  );
};

export default ProcessingToast;
