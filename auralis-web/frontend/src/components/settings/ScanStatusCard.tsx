/**
 * ScanStatusCard - Live auto-scanner status widget for the Library settings tab
 *
 * Shows real-time scan progress, last scan results, and a "Scan Now" button.
 * Subscribes directly to WebSocket scan events via useScanProgress().
 */

import React from 'react';
import {
  Box,
  LinearProgress,
  Typography,
  Divider,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow as ScanNowIcon,
  FolderOff as FolderOffIcon,
} from '@mui/icons-material';
import { Button } from '@/design-system';
import { tokens } from '@/design-system';
import { useScanProgress } from '../../hooks/library/useScanProgress';

interface ScanStatusCardProps {
  /** Disable the Scan Now button (no folders configured) */
  disabled?: boolean;
  onScanNow: () => void;
}

export const ScanStatusCard: React.FC<ScanStatusCardProps> = ({ disabled = false, onScanNow }) => {
  const { isScanning, current, total, percentage, currentFile, lastResult } = useScanProgress();

  // --- No folders configured ---
  if (disabled) {
    return (
      <Box
        sx={{
          ...tokens.glass.subtle,
          borderRadius: tokens.borderRadius.sm,
          p: tokens.spacing.md,
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          color: tokens.colors.text.disabled,
        }}
      >
        <FolderOffIcon fontSize="small" />
        <Typography variant="body2" sx={{ color: tokens.colors.text.disabled }}>
          Add folders above to begin scanning
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        ...tokens.glass.subtle,
        borderRadius: tokens.borderRadius.sm,
        overflow: 'hidden',
      }}
    >
      {/* Scanning state */}
      {isScanning ? (
        <Box sx={{ p: tokens.spacing.md }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontWeight: 500 }}>
              Scanning…
            </Typography>
            <Typography variant="caption" sx={{ color: tokens.colors.text.metadata }}>
              {total > 0 ? `${current} / ${total}` : `${current} files`}
            </Typography>
          </Box>
          <LinearProgress
            variant={total > 0 ? 'determinate' : 'indeterminate'}
            value={percentage}
            sx={{
              borderRadius: 2,
              height: 4,
              backgroundColor: tokens.colors.opacityScale.accent.ultraLight,
              '& .MuiLinearProgress-bar': {
                background: `linear-gradient(90deg, ${tokens.colors.accent.primary}, ${tokens.colors.accent.secondary})`,
                borderRadius: 2,
              },
            }}
          />
          {currentFile && (
            <Tooltip title={currentFile} placement="bottom-start">
              <Typography
                variant="caption"
                sx={{
                  display: 'block',
                  mt: 0.75,
                  color: tokens.colors.text.metadata,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%',
                }}
              >
                {currentFile.split('/').pop() ?? currentFile}
              </Typography>
            </Tooltip>
          )}
        </Box>
      ) : (
        /* Idle state */
        <Box sx={{ p: tokens.spacing.md }}>
          {lastResult ? (
            <Box
              sx={{
                display: 'flex',
                gap: 2,
                flexWrap: 'wrap',
                alignItems: 'center',
                mb: 0,
              }}
            >
              <Typography variant="body2" sx={{ color: tokens.colors.semantic.success }}>
                +{lastResult.filesAdded} added
              </Typography>
              {lastResult.filesRemoved > 0 && (
                <Typography variant="body2" sx={{ color: tokens.colors.semantic.error }}>
                  −{lastResult.filesRemoved} removed
                </Typography>
              )}
              <Typography variant="body2" sx={{ color: tokens.colors.text.metadata }}>
                ({lastResult.duration.toFixed(1)}s)
              </Typography>
            </Box>
          ) : (
            <Typography variant="body2" sx={{ color: tokens.colors.text.metadata }}>
              No scans yet
            </Typography>
          )}
        </Box>
      )}

      {/* Divider + Scan Now button (only when idle) */}
      {!isScanning && (
        <>
          <Divider sx={{ borderColor: tokens.colors.opacityScale.accent.ultraLight }} />
          <Box sx={{ p: tokens.spacing.sm, display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="ghost"
              size="sm"
              startIcon={<ScanNowIcon fontSize="small" />}
              onClick={onScanNow}
              sx={{ color: tokens.colors.accent.primary }}
            >
              Scan Now
            </Button>
          </Box>
        </>
      )}
    </Box>
  );
};

export default ScanStatusCard;
