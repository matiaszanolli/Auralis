/**
 * DropZoneIcon - Icon rendering for drop zone states
 *
 * Displays appropriate icon based on scanning, dragging, or idle state.
 */

import React from 'react';
import { Box } from '@mui/material';
import { CloudUpload, FolderOpen, CheckCircle } from '@mui/icons-material';
import { tokens } from '@/design-system/tokens';

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
            color: tokens.colors.accent.success,
            animation: 'fadeIn 0.3s ease',
          }}
        />
      ) : isDragging ? (
        <CloudUpload
          sx={{
            fontSize: 64,
            color: tokens.colors.accent.purple,
            animation: 'bounce 1s ease infinite',
          }}
        />
      ) : (
        <FolderOpen
          sx={{
            fontSize: 64,
            color: tokens.colors.text.disabled,
            transition: 'color 0.3s ease',
          }}
        />
      )}
    </Box>
  );
};
