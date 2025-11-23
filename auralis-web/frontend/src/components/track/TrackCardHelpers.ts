/**
 * TrackCard Helper Functions
 *
 * Utility functions for TrackCard component:
 * - Color selection for album placeholders
 * - Duration formatting
 */

import { gradients } from '../library/Styles/Color.styles';

/**
 * Generate consistent color from album name for placeholders
 * Uses simple hash function to pick from gradient palette
 */
export const getAlbumColor = (albumName: string | undefined | null): string => {
  const gradientList = [
    gradients.aurora, // Purple
    gradients.gradientPink, // Pink
    gradients.gradientBlue, // Blue
    gradients.gradientGreen, // Green
    gradients.gradientSunset, // Sunset
    gradients.gradientTeal, // Ocean/Teal
    gradients.gradientPastel, // Pastel
    gradients.gradientRose, // Rose
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
