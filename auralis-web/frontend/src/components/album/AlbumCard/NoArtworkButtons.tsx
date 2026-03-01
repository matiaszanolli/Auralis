/**
 * NoArtworkButtons Component
 *
 * Shows download/extract buttons when album has no artwork
 * Allows users to retrieve artwork from online sources or audio files
 */

import React from 'react';

import { CloudDownload, ImageSearch } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { IconButton, Tooltip } from '@/design-system';
import { Box } from '@mui/material';

export interface NoArtworkButtonsProps {
  show: boolean;
  onDownload: (e: React.MouseEvent) => void;
  onExtract: (e: React.MouseEvent) => void;
  isDownloading?: boolean;
  isExtracting?: boolean;
}

export const NoArtworkButtons: React.FC<NoArtworkButtonsProps> = ({
  show,
  onDownload,
  onExtract,
  isDownloading = false,
  isExtracting = false,
}) => {
  if (!show) return null;

  return (
    <Box
      sx={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        p: 1,
        background: 'linear-gradient(to top, rgba(0,0,0,0.42), transparent)',
        display: 'flex',
        gap: 0.5,
        justifyContent: 'center',
      }}
    >
      <Tooltip title="Download from online sources">
        <IconButton
          size="small"
          onClick={onDownload}
          disabled={isDownloading}
          sx={{
            color: tokens.colors.text.primary,
            background: tokens.gradients.aurora,
            '&:hover': { background: tokens.gradients.decorative.electricPurple },
          }}
        >
          <CloudDownload fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Extract from audio files">
        <IconButton
          size="small"
          onClick={onExtract}
          disabled={isExtracting}
          sx={{
            color: tokens.colors.text.primary,
            background: tokens.colors.opacityScale.accent.light,
            '&:hover': { background: tokens.colors.opacityScale.accent.standard },
          }}
        >
          <ImageSearch fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
};

export default NoArtworkButtons;
