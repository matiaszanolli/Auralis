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

import { ArtworkContainer } from './ArtworkContainer';
import { AlbumInfo } from './AlbumInfo';
import { useArtworkHandlers } from './useArtworkHandlers';
import { tokens } from '@/design-system';
import { Card } from '@/design-system';

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
        borderRadius: 3, // Increased from 2 (16px → 12px, using tokens.borderRadius.lg)
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        background: tokens.colors.bg.level3,
        // Removed border, using shadow for depth instead
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)', // Resting shadow for subtle depth
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        '&:hover': {
          transform: 'translateY(-4px)',
          // Elevation increase + background brightness +3%
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.25)',
          background: tokens.colors.bg.level4, // +3% brightness via level4
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
