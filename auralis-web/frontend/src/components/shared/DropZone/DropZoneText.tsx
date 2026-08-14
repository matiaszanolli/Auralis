/**
 * DropZoneText - Text content for drop zone
 *
 * Displays dynamic text based on scanning, dragging, or idle state.
 */

import { Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

interface DropZoneTextProps {
  isDragging: boolean;
  scanning: boolean;
}

export const DropZoneText = ({ isDragging, scanning }: DropZoneTextProps) => {
  return (
    <>
      <Typography
        variant="h6"
        sx={{
          fontWeight: tokens.typography.fontWeight.semibold,
          color: isDragging ? tokens.colors.accent.primary : themeVars.textPrimary,
          mb: 1,
          transition: tokens.transitions.color,
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
          color: themeVars.textSecondary,
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
            // #4635: 11px informational text, not decoration — AA 4.5:1.
            color: themeVars.textMuted,
            fontSize: 11,
          }}
        >
          Supported: MP3, FLAC, WAV, OGG, M4A, AAC, WMA
        </Typography>
      )}
    </>
  );
};
