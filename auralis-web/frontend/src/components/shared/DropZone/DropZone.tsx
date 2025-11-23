/**
 * DropZone Component
 * ~~~~~~~~~~~~~~~~~~
 *
 * Drag-and-drop zone for folder import.
 * Supports both drag-and-drop and click-to-browse functionality.
 */

import React, { useCallback, useRef } from 'react';
import { Box, Typography } from '@mui/material';
import { CloudUpload, FolderOpen, CheckCircle } from '@mui/icons-material';
import { tokens } from '@/design-system/tokens';
import { DropZonePaper } from './DropZoneStyles';
import { useDropZone } from './useDropZone';

interface DropZoneProps {
  onFolderDrop: (folderPath: string) => void;
  onFolderSelect?: (folderPath: string) => void;
  disabled?: boolean;
  scanning?: boolean;
}

/**
 * DropZone - Drag-and-drop area for music folder import
 *
 * Features:
 * - Drag-and-drop support for folders and files
 * - Click-to-browse fallback for browsers without drag-drop
 * - Visual feedback during dragging
 * - Scanning state indication
 * - Smooth animations and transitions
 *
 * @example
 * ```tsx
 * <DropZone
 *   onFolderDrop={handleFolderDrop}
 *   onFolderSelect={handleFolderSelect}
 *   scanning={isScanning}
 * />
 * ```
 */
export const DropZone: React.FC<DropZoneProps> = ({
  onFolderDrop,
  onFolderSelect,
  disabled = false,
  scanning = false,
}) => {
  const dropZoneRef = useRef<HTMLDivElement>(null);
  const { isDragging, handleDragEnter, handleDragLeave, handleDragOver, handleDrop } =
    useDropZone(disabled, scanning);

  const handleDropWrapper = useCallback(
    (e: React.DragEvent) => {
      handleDrop(e, onFolderDrop);
    },
    [handleDrop, onFolderDrop]
  );

  const handleClick = useCallback(() => {
    if (disabled || scanning) return;

    // Trigger folder selection dialog
    if (onFolderSelect) {
      // In web browser, show input prompt
      const folderPath = prompt('Enter folder path to scan:');
      if (folderPath) {
        onFolderSelect(folderPath);
      }
    }
  }, [disabled, scanning, onFolderSelect]);

  return (
    <DropZonePaper
      ref={dropZoneRef}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDropWrapper}
      onClick={handleClick}
      $isDragging={isDragging}
      $disabled={disabled}
      $scanning={scanning}
    >
      {/* Icon */}
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

      {/* Text */}
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
    </DropZonePaper>
  );
};

export default DropZone;
