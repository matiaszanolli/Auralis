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
    if (stats.cacheHit) return colors.accent.success;
    if (stats.status === 'analyzing') return colors.accent.purple;
    return '#667eea'; // primary purple
  };

  return (
    <Fade in={show}>
      <Paper
        elevation={8}
        sx={{
          position: 'fixed',
          bottom: 100, // Above player bar
          right: 24,
          width: 280,
          backgroundColor: 'rgba(26, 31, 58, 0.95)',
          backdropFilter: 'blur(20px)',
          borderRadius: '12px',
          border: '1px solid rgba(139, 146, 176, 0.2)',
          overflow: 'hidden',
          zIndex: 1300,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)'
        }}
      >
        <Box sx={{ p: 2 }}>
          {/* Header with icon */}
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1.5 }}>
            <AutoAwesome
              sx={{
                fontSize: 20,
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
                color: colors.text.primary,
                fontWeight: 600,
                fontSize: '13px'
              }}
            >
              {getStatusText()}
            </Typography>
          </Stack>

          {/* Stats chips */}
          <Stack direction="row" spacing={1} flexWrap="wrap" gap={0.5}>
            {stats.cacheHit && (
              <Chip
                icon={<TrendingUp sx={{ fontSize: 14 }} />}
                label="8x faster"
                size="small"
                sx={{
                  height: 22,
                  backgroundColor: 'rgba(76, 175, 80, 0.1)',
                  color: colors.accent.success,
                  fontSize: '11px',
                  '& .MuiChip-icon': {
                    color: colors.accent.success
                  }
                }}
              />
            )}

            {stats.processingSpeed && stats.processingSpeed > 1 && (
              <Chip
                icon={<Speed sx={{ fontSize: 14 }} />}
                label={`${stats.processingSpeed.toFixed(1)}x RT`}
                size="small"
                sx={{
                  height: 22,
                  backgroundColor: 'rgba(102, 126, 234, 0.1)',
                  color: colors.accent.purple,
                  fontSize: '11px',
                  '& .MuiChip-icon': {
                    color: colors.accent.purple
                  }
                }}
              />
            )}

            {stats.currentChunk !== undefined && (
              <Chip
                icon={<Memory sx={{ fontSize: 14 }} />}
                label={`${((stats.currentChunk / (stats.totalChunks || 1)) * 100).toFixed(0)}%`}
                size="small"
                sx={{
                  height: 22,
                  backgroundColor: 'rgba(139, 146, 176, 0.1)',
                  color: colors.text.secondary,
                  fontSize: '11px',
                  '& .MuiChip-icon': {
                    color: colors.text.secondary
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
