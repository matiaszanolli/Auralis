import { useState, useCallback, type SyntheticEvent } from 'react';

/**
 * useTrackImage - Manages album art thumbnail display
 *
 * Handles:
 * - Image loading state
 * - Image error fallback
 *
 * The failure is remembered per URL, not as one flag for the life of the row: art that
 * 404'd before it was extracted or downloaded gets a new `?v=N` once `artwork_updated`
 * arrives, and that URL has to be tried (#5894).
 */
export const useTrackImage = () => {
  // The src that failed; `null` = nothing failed. The attribute string is compared, so it
  // matches the URL the row passed in.
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  const handleImageError = useCallback((event?: SyntheticEvent<HTMLImageElement>) => {
    setFailedSrc(event?.currentTarget.getAttribute('src') ?? '');
  }, []);

  const shouldShowImage = useCallback(
    (albumArt: string | undefined) => {
      // '' = a failure reported without its URL: hide, as the old single flag did.
      return !!(albumArt && failedSrc !== albumArt && failedSrc !== '');
    },
    [failedSrc]
  );

  return {
    imageError: failedSrc !== null,
    handleImageError,
    shouldShowImage,
  };
};
