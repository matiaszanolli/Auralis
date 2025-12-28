/**
 * EraSection Component
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * Displays a group of albums from a specific era with a header.
 * Used to organize albums chronologically in the albums view.
 *
 * Design: Section header (era label) followed by horizontal album row.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';

interface Album {
  id: number;
  title: string;
  artist: string;
  artworkUrl?: string;
  trackCount?: number;
  totalDuration?: number;
  year?: number;
}

interface EraSectionProps {
  /** Era label (e.g., "1978 - 1982") */
  label: string;
  /** Albums in this era */
  albums: Album[];
  /** Map of album IDs to fingerprints */
  fingerprints: Map<number, AudioFingerprint | null>;
  /** Callback when an album is clicked */
  onAlbumClick?: (albumId: number) => void;
  /** Callback when an album is hovered */
  onAlbumHover?: (albumId: number, albumTitle?: string, albumArtist?: string) => void;
  /** Callback when album hover ends */
  onAlbumHoverEnd?: () => void;
}

/**
 * EraSection - Era header with album grid
 */
export const EraSection: React.FC<EraSectionProps> = ({
  label,
  albums,
  fingerprints,
  onAlbumClick,
  onAlbumHover,
  onAlbumHoverEnd,
}) => {
  // Don't render empty eras
  if (albums.length === 0) {
    return null;
  }

  return (
    <Box
      sx={{
        mb: tokens.spacing.xl,
      }}
    >
      {/* Era Header */}
      <Typography
        variant="h6"
        sx={{
          fontSize: tokens.typography.fontSize.lg,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.text.secondary,
          mb: tokens.spacing.md,
          pl: tokens.spacing.xs,
          // Subtle left border accent
          borderLeft: `3px solid ${tokens.colors.accent.primary}`,
          paddingLeft: tokens.spacing.md,
        }}
      >
        {label}
      </Typography>

      {/* Album Grid for this era */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, 200px)',
          gap: tokens.spacing.group,
        }}
      >
        {albums.map((album) => {
          const fingerprint = fingerprints.get(album.id) ?? undefined;

          return (
            <AlbumCard
              key={album.id}
              albumId={album.id}
              title={album.title}
              artist={album.artist}
              hasArtwork={!!album.artworkUrl}
              trackCount={album.trackCount}
              duration={album.totalDuration}
              year={album.year}
              fingerprint={fingerprint}
              onClick={() => onAlbumClick?.(album.id)}
              onHoverEnter={(id) => onAlbumHover?.(id, album.title, album.artist)}
              onHoverLeave={onAlbumHoverEnd}
            />
          );
        })}
      </Box>
    </Box>
  );
};

export default EraSection;
