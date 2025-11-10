/**
 * Processing Toast - Subtle, non-intrusive processing status indicator
 *
 * Shows real-time processing stats in a compact bottom-right toast
 * that doesn't block the UI or interrupt the user experience.
 */

import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Fade,
  Stack,
  Chip
} from '@mui/material';
import {
  AutoAwesome,
  Speed,
  Memory,
  TrendingUp
} from '@mui/icons-material';
import { colors, gradients } from '../theme/auralisTheme';
import { tokens } from '@/design-system/tokens';

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
    if (stats.cacheHit) return tokens.colors.accent.success;
    if (stats.status === 'analyzing') return tokens.colors.accent.purple;
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
          <Stack direction="row" spacing={tokens.spacing.xs} flexWrap="wrap" gap={tokens.spacing.xs}>
            {stats.cacheHit && (
              <Chip
                icon={<TrendingUp sx={{ fontSize: tokens.typography.fontSize.sm }} />}
                label="8x faster"
                size="small"
                sx={{
                  height: '22px',
                  backgroundColor: `${tokens.colors.accent.success}1A`,
                  color: tokens.colors.accent.success,
                  fontSize: tokens.typography.fontSize.xs,
                  '& .MuiChip-icon': {
                    color: tokens.colors.accent.success
                  }
                }}
              />
            )}

            {stats.processingSpeed && stats.processingSpeed > 1 && (
              <Chip
                icon={<Speed sx={{ fontSize: tokens.typography.fontSize.sm }} />}
                label={`${stats.processingSpeed.toFixed(1)}x RT`}
                size="small"
                sx={{
                  height: '22px',
                  backgroundColor: `${tokens.colors.accent.primary}1A`,
                  color: tokens.colors.accent.purple,
                  fontSize: tokens.typography.fontSize.xs,
                  '& .MuiChip-icon': {
                    color: tokens.colors.accent.purple
                  }
                }}
              />
            )}

            {stats.currentChunk !== undefined && (
              <Chip
                icon={<Memory sx={{ fontSize: tokens.typography.fontSize.sm }} />}
                label={`${((stats.currentChunk / (stats.totalChunks || 1)) * 100).toFixed(0)}%`}
                size="small"
                sx={{
                  height: '22px',
                  backgroundColor: `${tokens.colors.text.secondary}1A`,
                  color: tokens.colors.text.secondary,
                  fontSize: tokens.typography.fontSize.xs,
                  '& .MuiChip-icon': {
                    color: tokens.colors.text.secondary
                  }
                }}
              />
            )}
          </Stack>
        </Box>
      </Paper>
    </Fade>
  );
};

export default ProcessingToast;
