/**
 * AlbumCard Component (Refactored)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Album card with artwork, title, artist, and artwork management options.
 * Includes buttons to download/extract artwork when missing.
 *
 * Modular structure:
 * - ArtworkContainer - Artwork image + overlays + menu
 * - AlbumInfo - Title, artist, metadata
 * - useArtworkHandlers - Artwork operation logic
 */

import React, { useState } from 'react';
import { Card } from '@mui/material';
import { ArtworkContainer } from './ArtworkContainer';
import { AlbumInfo } from './AlbumInfo';
import { useArtworkHandlers } from './useArtworkHandlers';
import { auroraOpacity } from '../../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

export interface AlbumCardProps {
  albumId: number;
  title: string;
  artist: string;
  hasArtwork?: boolean;
  trackCount?: number;
  duration?: number;
  year?: number;
  onClick?: () => void;
  onArtworkUpdated?: () => void;
}

export const AlbumCard: React.FC<AlbumCardProps> = ({
  albumId,
  title,
  artist,
  hasArtwork = false,
  trackCount = 0,
  duration,
  year,
  onClick,
  onArtworkUpdated,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const {
    downloading,
    extracting,
    handleDownloadArtwork,
    handleExtractArtwork,
    handleDeleteArtwork,
  } = useArtworkHandlers(albumId, onArtworkUpdated);

  return (
    <Card
      sx={{
        position: 'relative',
        borderRadius: 2,
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        background: tokens.colors.bg.level3,
        border: `1px solid ${tokens.colors.border.light}`,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: `0 8px 24px ${auroraOpacity.standard}`,
          border: `1px solid ${auroraOpacity.strong}`,
        },
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={onClick}
    >
      {/* Artwork Section with Overlays */}
      <ArtworkContainer
        albumId={albumId}
        hasArtwork={hasArtwork}
        isHovered={isHovered}
        isDownloading={downloading}
        isExtracting={extracting}
        onPlay={onClick || (() => {})}
        onMenuOpen={() => setMenuOpen(true)}
        onMenuClose={() => setMenuOpen(false)}
        onDownload={async (e) => {
          e.stopPropagation();
          await handleDownloadArtwork();
        }}
        onExtract={async (e) => {
          e.stopPropagation();
          await handleExtractArtwork();
        }}
        onDelete={handleDeleteArtwork}
      />

      {/* Album Info Section */}
      <AlbumInfo title={title} artist={artist} trackCount={trackCount} duration={duration} year={year} />
    </Card>
  );
};

export default AlbumCard;
