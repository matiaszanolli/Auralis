/**
 * RecentlyTouchedSection Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Displays recently accessed albums in a horizontal scrollable section.
 * Shows at the top of the Albums view for quick access to recent browsing.
 *
 * Design: Horizontal scroll with smaller album cards (compact view).
 * Philosophy: "Where you left off" - contextual continuity for browsing.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import { useAlbumFingerprints } from '@/hooks/fingerprint/useAlbumFingerprint';
import type { RecentlyTouchedEntry } from '@/hooks/library/useRecentlyTouched';

interface RecentlyTouchedSectionProps {
  /** List of recently touched albums */
  recentAlbums: RecentlyTouchedEntry[];
  /** Callback when an album is clicked */
  onAlbumClick?: (albumId: number) => void;
  /** Callback when an album is hovered */
  onAlbumHover?: (albumId: number, albumTitle?: string, albumArtist?: string) => void;
  /** Callback when album hover ends */
  onAlbumHoverEnd?: () => void;
}

/**
 * RecentlyTouchedSection - Horizontal scroll of recent albums
 *
 * Shows nothing if no recent albums exist.
 * Limited to first 8 albums for visual balance.
 */
export const RecentlyTouchedSection: React.FC<RecentlyTouchedSectionProps> = ({
  recentAlbums,
  onAlbumClick,
  onAlbumHover,
  onAlbumHoverEnd,
}) => {
  // Don't render if no recent albums
  if (recentAlbums.length === 0) {
    return null;
  }

  // Limit to 8 albums for visual balance
  const displayedAlbums = recentAlbums.slice(0, 8);

  // Get album IDs for fingerprint batch fetch
  const albumIds = displayedAlbums.map(album => album.albumId);
  const { fingerprints } = useAlbumFingerprints(albumIds);

  return (
    <Box
      sx={{
        mb: tokens.spacing.xl,
        pb: tokens.spacing.lg,
        borderBottom: `1px solid ${tokens.colors.border.light}`,
      }}
    >
      {/* Section Header */}
      <Typography
        variant="h6"
        sx={{
          fontSize: tokens.typography.fontSize.md,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.text.primary,
          mb: tokens.spacing.md,
          display: 'flex',
          alignItems: 'center',
          gap: tokens.spacing.sm,
        }}
      >
        <span style={{ opacity: 0.7 }}>🕐</span>
        Recently Touched
      </Typography>

      {/* Horizontal Scroll Container */}
      <Box
        sx={{
          display: 'flex',
          gap: tokens.spacing.md,
          overflowX: 'auto',
          pb: tokens.spacing.sm, // Space for scrollbar
          // Hide scrollbar but keep functionality
          scrollbarWidth: 'thin',
          '&::-webkit-scrollbar': {
            height: '6px',
          },
          '&::-webkit-scrollbar-track': {
            background: tokens.colors.bg.tertiary,
            borderRadius: tokens.borderRadius.full,
          },
          '&::-webkit-scrollbar-thumb': {
            background: tokens.colors.border.light,
            borderRadius: tokens.borderRadius.full,
            '&:hover': {
              background: tokens.colors.accent.primary,
            },
          },
        }}
      >
        {displayedAlbums.map((album) => {
          const fingerprint = fingerprints.get(album.albumId) ?? undefined;

          return (
            <Box
              key={album.albumId}
              sx={{
                flexShrink: 0,
                width: '160px', // Smaller than grid cards (200px)
              }}
            >
              <AlbumCard
                albumId={album.albumId}
                title={album.albumTitle}
                artist={album.artist}
                hasArtwork={true} // Assume artwork exists for recent
                fingerprint={fingerprint}
                onClick={() => onAlbumClick?.(album.albumId)}
                onHoverEnter={(id) => onAlbumHover?.(id, album.albumTitle, album.artist)}
                onHoverLeave={onAlbumHoverEnd}
              />
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};

export default RecentlyTouchedSection;
