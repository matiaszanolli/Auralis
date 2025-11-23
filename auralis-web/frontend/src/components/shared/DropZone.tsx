/**
 * DropZone Component
 * ~~~~~~~~~~~~~~~~~~
 *
 * Drag-and-drop zone for folder import.
 * Supports both drag-and-drop and click-to-browse functionality.
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Paper,
  alpha,
} from '@mui/material';
import {
  CloudUpload,
  FolderOpen,
  CheckCircle,
} from '@mui/icons-material';
import { gradients } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

interface DropZoneProps {
  onFolderDrop: (folderPath: string) => void;
  onFolderSelect?: (folderPath: string) => void;
  disabled?: boolean;
  scanning?: boolean;
}

export const DropZone: React.FC<DropZoneProps> = ({
  onFolderDrop,
  onFolderSelect,
  disabled = false,
  scanning = false,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);
  const dropZoneRef = useRef<HTMLDivElement>(null);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled || scanning) return;

    setDragCounter((prev) => prev + 1);

    // Check if we're dragging files
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  }, [disabled, scanning]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled || scanning) return;

    setDragCounter((prev) => {
      const newCounter = prev - 1;
      if (newCounter === 0) {
        setIsDragging(false);
      }
      return newCounter;
    });
  }, [disabled, scanning]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled || scanning) return;

    // Set dropEffect to indicate this is a copy operation
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'copy';
    }
  }, [disabled, scanning]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    setIsDragging(false);
    setDragCounter(0);

    if (disabled || scanning) return;

    // Get dropped files/folders
    const items = Array.from(e.dataTransfer.items);

    // Process the first item (should be a folder)
    if (items.length > 0) {
      const item = items[0];

      // Check if it's a file or directory
      if (item.kind === 'file') {
        const entry = item.webkitGetAsEntry();

        if (entry && entry.isDirectory) {
          // Get the full path
          const folderPath = (entry as any).fullPath || entry.name;
          onFolderDrop(folderPath);
        } else if (entry && entry.isFile) {
          // If it's a file, get its parent directory
          const file = item.getAsFile();
          if (file) {
            // Extract folder path from file path
            const pathParts = file.webkitRelativePath || file.name;
            const folderPath = pathParts.substring(0, pathParts.lastIndexOf('/')) || './';
            onFolderDrop(folderPath);
          }
        }
      }
    }
  }, [disabled, scanning, onFolderDrop]);

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
    <Paper
      ref={dropZoneRef}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
      sx={{
        position: 'relative',
        p: 4,
        borderRadius: 3,
        border: `2px dashed ${
          isDragging
            ? tokens.colors.accent.purple
            : scanning
            ? alpha(tokens.colors.text.secondary, 0.3)
            : alpha(tokens.colors.text.disabled, 0.2)
        }`,
        background: isDragging
          ? alpha(tokens.colors.accent.purple, 0.05)
          : scanning
          ? alpha(tokens.colors.bg.hover, 0.5)
          : 'transparent',
        cursor: disabled || scanning ? 'not-allowed' : 'pointer',
        transition: 'all 0.3s ease',
        textAlign: 'center',
        overflow: 'hidden',
        opacity: disabled ? 0.5 : 1,

        ...((!disabled && !scanning) && {
          '&:hover': {
            borderColor: tokens.colors.accent.purple,
            background: alpha(tokens.colors.accent.purple, 0.02),
            transform: 'scale(1.01)',
          },
        }),

        ...(isDragging && {
          '&::before': {
            content: '""',
            position: 'absolute',
            inset: 0,
            background: gradients.aurora,
            opacity: 0.05,
            animation: 'pulse 2s ease-in-out infinite',
          },
        }),

        '@keyframes pulse': {
          '0%, 100%': { opacity: 0.05 },
          '50%': { opacity: 0.1 },
        },
      }}
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

      {/* Bounce animation for upload icon */}
      <style>
        {`
          @keyframes bounce {
            0%, 100% {
              transform: translateY(0);
            }
            50% {
              transform: translateY(-10px);
            }
          }
          @keyframes fadeIn {
            from {
              opacity: 0;
              transform: scale(0.8);
            }
            to {
              opacity: 1;
              transform: scale(1);
            }
          }
        `}
      </style>
    </Paper>
  );
};
