/**
 * useProgressiveImageLoader Hook
 *
 * Manages progressive image loading with retry logic, exponential backoff,
 * and state management for loaded/error states.
 */

import { useState, useEffect, useRef } from 'react';

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

  // Callbacks live in refs so an inline arrow from the caller does not restart
  // the load (and its retry budget) on every render.
  const onLoadRef = useRef(onLoad);
  const onErrorRef = useRef(onError);
  onLoadRef.current = onLoad;
  onErrorRef.current = onError;

  useEffect(() => {
    // Reset states when src changes
    setImageLoaded(false);
    setImageError(false);
    setImageSrc(null);

    if (!src) {
      setImageError(true);
      return;
    }

    // The retry count is local to this run of the effect. It used to be React
    // state that the effect both depended on and reset to 0 at its top, so every
    // retry restarted the sequence and a permanently failing image retried
    // forever (#5353); the backoff timer was also never cleared on unmount/src change.
    let attempt = 0;
    let img: HTMLImageElement | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    const load = () => {
      const current = new Image();
      img = current;

      current.onload = () => {
        setImageSrc(src);
        setImageLoaded(true);
        onLoadRef.current?.();
      };

      current.onerror = () => {
        // Retry logic with exponential backoff
        if (retryOnError && attempt < maxRetries) {
          const retryDelay = Math.min(1000 * Math.pow(2, attempt), 3000);
          attempt += 1;
          retryTimer = setTimeout(load, retryDelay);
        } else {
          setImageError(true);
          onErrorRef.current?.();
        }
      };

      // Add cache busting for retries
      const retrySeparator = src.includes('?') ? '&' : '?';
      current.src = attempt > 0 ? `${src}${retrySeparator}retry=${attempt}` : src;
    };

    load();

    // Cleanup
    return () => {
      clearTimeout(retryTimer);
      if (img) {
        img.onload = null;
        img.onerror = null;
      }
    };
  }, [src, retryOnError, maxRetries]);

  return {
    imageLoaded,
    imageError,
    imageSrc,
  };
};
