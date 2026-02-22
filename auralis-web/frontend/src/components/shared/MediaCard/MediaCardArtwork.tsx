/**
 * MediaCardArtwork Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Artwork container with responsive aspect ratio and placeholder support.
 * Unified component for both track and album artwork display.
 *
 * Placeholder Strategy:
 * 1. If fingerprint provided → Use fingerprintToGradient (sonic identity)
 * 2. Else → Use hash-based gradient (fallback for non-fingerprinted items)
 */

import React from 'react';
import { Box } from '@mui/material';
import { tokens } from '@/design-system';
import { MediaCardVariant } from './MediaCard.types';
import { fingerprintToGradientSafe, type AudioFingerprint } from '@/utils/fingerprintToGradient';

interface MediaCardArtworkProps {
  /** Artwork URL (optional) */
  artworkUrl?: string;
  /** Fallback text for placeholder (album or track name) */
  fallbackText: string;
  /** Card variant (affects placeholder color) */
  variant: MediaCardVariant;
  /** Audio fingerprint for gradient generation (optional) */
  fingerprint?: Partial<AudioFingerprint>;
  /** Child elements (overlay) */
  children?: React.ReactNode;
}

/**
 * Generate placeholder color based on text hash
 * (Extracted from TrackCardHelpers.getAlbumColor)
 * Used as fallback when no fingerprint is available
 */
const getPlaceholderColor = (text: string | null | undefined): string => {
  // Use design-system tokens so placeholder gradients stay in sync with the
  // color system (fixes #2551: hardcoded hex values bypassed tokens.gradients).
  const colors = [
    tokens.gradients.aurora,                        // violet → indigo
    tokens.gradients.decorative.gradientPink,       // #f093fb → #f5576c
    tokens.gradients.decorative.gradientBlue,       // #4facfe → #00f2fe
    tokens.gradients.decorative.gradientGreen,      // #43e97b → #38f9d7
    tokens.gradients.decorative.gradientSunset,     // #fa709a → #fee140
  ];

  // Handle null/undefined text with fallback
  const safeText = text || 'Unknown';

  const hash = safeText.split('').reduce((acc, char) => {
    return char.charCodeAt(0) + ((acc << 5) - acc);
  }, 0);

  return colors[Math.abs(hash) % colors.length];
};

/**
 * Get placeholder gradient
 * Priority: fingerprint > hash-based fallback
 */
const getPlaceholderGradient = (
  fingerprint: Partial<AudioFingerprint> | undefined,
  fallbackText: string
): string => {
  if (fingerprint) {
    // Use fingerprint-based gradient (sonic identity)
    return fingerprintToGradientSafe(fingerprint);
  }

  // Fallback to hash-based color
  return getPlaceholderColor(fallbackText);
};

/**
 * MediaCardArtwork - Artwork container with placeholder fallback
 */
export const MediaCardArtwork: React.FC<MediaCardArtworkProps> = ({
  artworkUrl,
  fallbackText,
  variant,
  fingerprint,
  children,
}) => {
  return (
    <Box
      sx={{
        position: 'relative',
        paddingTop: '100%', // 1:1 aspect ratio
        borderRadius: `${tokens.borderRadius.lg}px ${tokens.borderRadius.lg}px 0 0`,
        overflow: 'hidden',
        background: artworkUrl
          ? `url(${artworkUrl}) center/cover no-repeat`
          : getPlaceholderGradient(fingerprint, fallbackText),
      }}
    >
      {/* Overlay container (play button, badges, etc.) */}
      {children && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
          }}
        >
          {children}
        </Box>
      )}
    </Box>
  );
};
