/**
 * useProgressiveImageLoader Hook
 *
 * Manages progressive image loading with retry logic, exponential backoff,
 * and state management for loaded/error states.
 */

import { useState, useEffect } from 'react';

interface UseProgressiveImageLoaderProps {
  src: string;
  retryOnError?: boolean;
  maxRetries?: number;
  onLoad?: () => void;
  onError?: () => void;
}

export const useProgressiveImageLoader = ({
  src,
  retryOnError = true,
  maxRetries = 2,
  onLoad,
  onError,
}: UseProgressiveImageLoaderProps) => {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    // Reset states when src changes
    setImageLoaded(false);
    setImageError(false);
    setImageSrc(null);
    setRetryCount(0);

    if (!src) {
      setImageError(true);
      return;
    }

    // Preload image
    const img = new Image();

    img.onload = () => {
      setImageSrc(src);
      setImageLoaded(true);
      onLoad?.();
    };

    img.onerror = () => {
      // Retry logic with exponential backoff
      if (retryOnError && retryCount < maxRetries) {
        const retryDelay = Math.min(1000 * Math.pow(2, retryCount), 3000);
        setTimeout(() => {
          setRetryCount((prev) => prev + 1);
        }, retryDelay);
      } else {
        setImageError(true);
        onError?.();
      }
    };

    // Add cache busting for retries
    img.src = retryCount > 0 ? `${src}?retry=${retryCount}` : src;

    // Cleanup
    return () => {
      img.onload = null;
      img.onerror = null;
    };
  }, [src, onLoad, onError, retryCount, retryOnError, maxRetries]);

  return {
    imageLoaded,
    imageError,
    imageSrc,
  };
};
