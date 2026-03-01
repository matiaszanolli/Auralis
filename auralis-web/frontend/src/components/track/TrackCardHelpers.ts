/**
 * TrackCard Helper Functions
 *
 * Utility functions for TrackCard component:
 * - Color selection for album placeholders
 * - Duration formatting
 */

import { tokens } from '@/design-system';

/**
 * Generate consistent color from album name for placeholders
 * Uses simple hash function to pick from gradient palette
 */
export const getAlbumColor = (albumName: string | undefined | null): string => {
  const gradientList = [
    tokens.gradients.aurora, // Purple
    tokens.gradients.decorative.gradientPink, // Pink
    tokens.gradients.decorative.gradientBlue, // Blue
    tokens.gradients.decorative.gradientGreen, // Green
    tokens.gradients.decorative.gradientSunset, // Sunset
    tokens.gradients.decorative.gradientTeal, // Ocean/Teal
    tokens.gradients.decorative.gradientPastel, // Pastel
    tokens.gradients.decorative.gradientRose, // Rose
  ];

  // Use default album name if not provided
  const name = albumName || 'Unknown Album';

  // Simple hash function
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % gradientList.length;
  return gradientList[index];
};

/**
 * Format duration in MM:SS format
 */
export const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};
