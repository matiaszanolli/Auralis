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
import { Box } from '@mui/material';
import { AlbumArt } from '../AlbumArt';
import { PlayOverlay } from './PlayOverlay';
import { LoadingOverlay } from './LoadingOverlay';
import { NoArtworkButtons } from './NoArtworkButtons';
import { ArtworkMenu } from './ArtworkMenu';
import { ArtworkSquareContainer } from './ArtworkSquareContainer';
import { ArtworkMenuButton } from './ArtworkMenuButton';

// Shimmer overlay for placeholders (same as TrackCard)
const ShimmerOverlay: React.FC = () => (
  <Box
    className="shimmer-overlay"
    sx={{
      position: 'absolute',
      top: 0,
      left: '-100%',
      width: '100%',
      height: '100%',
      background:
        'linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.08) 50%, transparent 100%)',
      pointerEvents: 'none',
    }}
  />
);

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
      <ArtworkSquareContainer>
        {/* Album Artwork */}
        <AlbumArt albumId={albumId} size="100%" borderRadius={0} />

        {/* Shimmer overlay - only for placeholders (when no artwork) */}
        {!hasArtwork && <ShimmerOverlay />}

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
        <ArtworkMenuButton onClick={handleMenuOpen} />
      </ArtworkSquareContainer>

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
