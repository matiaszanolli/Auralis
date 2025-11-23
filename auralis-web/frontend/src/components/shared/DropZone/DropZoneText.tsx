/**
 * DropZoneText - Text content for drop zone
 *
 * Displays dynamic text based on scanning, dragging, or idle state.
 */

import React from 'react';
import { Typography } from '@mui/material';
import { tokens } from '@/design-system/tokens';

interface DropZoneTextProps {
  isDragging: boolean;
  scanning: boolean;
}

export const DropZoneText: React.FC<DropZoneTextProps> = ({ isDragging, scanning }) => {
  return (
    <>
      <Typography
        variant="h6"
        sx={{
          fontWeight: 600,
          color: isDragging ? tokens.colors.accent.purple : tokens.colors.text.primary,
          mb: 1,
          transition: 'color 0.3s ease',
        }}
      >
        {scanning
          ? 'Scanning...'
          : isDragging
          ? 'Drop folder here'
          : 'Drag & Drop Music Folder'}
      </Typography>

      <Typography
        variant="body2"
        sx={{
          color: tokens.colors.text.secondary,
          maxWidth: 400,
          mx: 'auto',
        }}
      >
        {scanning
          ? 'Please wait while we scan your music library'
          : isDragging
          ? 'Release to start scanning'
          : 'Drag a folder containing music files here, or click to browse'}
      </Typography>

      {/* Supported formats */}
      {!scanning && !isDragging && (
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            mt: 2,
            color: tokens.colors.text.disabled,
            fontSize: 11,
          }}
        >
          Supported: MP3, FLAC, WAV, OGG, M4A, AAC, WMA
        </Typography>
      )}
    </>
  );
};
