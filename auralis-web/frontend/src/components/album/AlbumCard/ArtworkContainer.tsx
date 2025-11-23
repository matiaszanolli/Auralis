/**
 * ArtworkContainer Component
 *
 * Container for album artwork with all overlays and controls:
 * - Album artwork image
 * - Play button overlay (on hover)
 * - Loading indicator
 * - No artwork buttons
 * - Options menu
 */

import React, { useState } from 'react';
import { Box, IconButton } from '@mui/material';
import { MoreVert } from '@mui/icons-material';
import { AlbumArt } from '../AlbumArt';
import { PlayOverlay } from './PlayOverlay';
import { LoadingOverlay } from './LoadingOverlay';
import { NoArtworkButtons } from './NoArtworkButtons';
import { ArtworkMenu } from './ArtworkMenu';
import { tokens } from '@/design-system/tokens';

export interface ArtworkContainerProps {
  albumId: number;
  hasArtwork: boolean;
  isHovered: boolean;
  isDownloading: boolean;
  isExtracting: boolean;
  onPlay: (e: React.MouseEvent) => void;
  onMenuOpen: (e: React.MouseEvent) => void;
  onMenuClose: () => void;
  onDownload: (e: React.MouseEvent) => void;
  onExtract: (e: React.MouseEvent) => void;
  onDelete: () => void;
}

export const ArtworkContainer: React.FC<ArtworkContainerProps> = ({
  albumId,
  hasArtwork,
  isHovered,
  isDownloading,
  isExtracting,
  onPlay,
  onMenuOpen,
  onMenuClose,
  onDownload,
  onExtract,
  onDelete,
}) => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuOpen = (e: React.MouseEvent<HTMLElement>) => {
    e.stopPropagation();
    setAnchorEl(e.currentTarget);
    onMenuOpen(e);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    onMenuClose();
  };

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDownload(e);
  };

  const handleExtract = (e: React.MouseEvent) => {
    e.stopPropagation();
    onExtract(e);
  };

  const handleDelete = () => {
    handleMenuClose();
    onDelete();
  };

  return (
    <>
      {/* Artwork Container */}
      <Box
        sx={{
          position: 'relative',
          width: '100%',
          paddingBottom: '100%', // Creates 1:1 (square) aspect ratio
          overflow: 'hidden',
          backgroundColor: tokens.colors.bg.primary,
          flexShrink: 0,
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
          }}
        >
          {/* Album Artwork */}
          <AlbumArt albumId={albumId} size="100%" borderRadius={0} />

          {/* Play Button Overlay */}
          <PlayOverlay isHovered={isHovered} onClick={onPlay} />

          {/* Loading Overlay */}
          <LoadingOverlay show={isDownloading || isExtracting} />

          {/* No Artwork Buttons */}
          <NoArtworkButtons
            show={!hasArtwork && !isDownloading && !isExtracting}
            onDownload={handleDownload}
            onExtract={handleExtract}
            isDownloading={isDownloading}
            isExtracting={isExtracting}
          />

          {/* Options Menu Button */}
          <IconButton
            onClick={handleMenuOpen}
            sx={{
              position: 'absolute',
              top: 8,
              right: 8,
              color: tokens.colors.text.primary,
              background: 'rgba(0, 0, 0, 0.19)',
              backdropFilter: 'blur(10px)',
              '&:hover': { background: 'rgba(0, 0, 0, 0.42)' },
            }}
          >
            <MoreVert />
          </IconButton>
        </Box>
      </Box>

      {/* Artwork Menu */}
      <ArtworkMenu
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={handleMenuClose}
        hasArtwork={hasArtwork}
        onDownload={() => {
          handleMenuClose();
          onDownload({} as React.MouseEvent);
        }}
        onExtract={() => {
          handleMenuClose();
          onExtract({} as React.MouseEvent);
        }}
        onDelete={handleDelete}
        isDownloading={isDownloading}
        isExtracting={isExtracting}
      />
    </>
  );
};

export default ArtworkContainer;
