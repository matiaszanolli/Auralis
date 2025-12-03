import { useState, useCallback } from 'react';

/**
 * useTrackImage - Manages album art thumbnail display
 *
 * Handles:
 * - Image loading state
 * - Image error fallback
 */
export const useTrackImage = () => {
  const [imageError, setImageError] = useState(false);

  const handleImageError = useCallback(() => {
    setImageError(true);
  }, []);

  const shouldShowImage = useCallback(
    (albumArt: string | undefined) => {
      return !!(albumArt && !imageError);
    },
    [imageError]
  );

  return {
    imageError,
    handleImageError,
    shouldShowImage,
  };
};
