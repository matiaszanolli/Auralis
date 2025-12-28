/**
 * DropZoneIcon - Icon rendering for drop zone states
 *
 * Displays appropriate icon based on scanning, dragging, or idle state.
 */

import React from 'react';
import { Box } from '@mui/material';
import { CloudUpload, FolderOpen, CheckCircle } from '@mui/icons-material';
import { tokens } from '@/design-system';

interface DropZoneIconProps {
  isDragging: boolean;
  scanning: boolean;
}

export const DropZoneIcon: React.FC<DropZoneIconProps> = ({ isDragging, scanning }) => {
  return (
    <Box
      sx={{
        mb: 2,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      {scanning ? (
        <CheckCircle
          sx={{
            fontSize: 64,
            color: tokens.colors.semantic.success,
            animation: 'fadeIn 0.45s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
          }}
        />
      ) : isDragging ? (
        <CloudUpload
          sx={{
            fontSize: 64,
            color: tokens.colors.accent.primary,
            // Style Guide §6.1: Slow, weighted motion - no bounce
            animation: 'breathe 2.5s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite',
          }}
        />
      ) : (
        <FolderOpen
          sx={{
            fontSize: 64,
            color: tokens.colors.text.disabled,
            transition: `color ${tokens.transitions.stateChange}`,
          }}
        />
      )}
    </Box>
  );
};
