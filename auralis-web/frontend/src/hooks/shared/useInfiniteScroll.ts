import { useState, useEffect, useCallback, useRef } from 'react';

interface UseInfiniteScrollOptions {
  threshold?: number;
  rootMargin?: string;
  onLoadMore: () => Promise<void>;
  hasMore: boolean;
  isLoading: boolean;
}

/**
 * Hook for infinite scroll functionality
 * Automatically loads more items when the user scrolls near the bottom
 */
export function useInfiniteScroll({
  threshold = 0.8,
  rootMargin = '100px',
  onLoadMore,
  hasMore,
  isLoading,
}: UseInfiniteScrollOptions) {
  const [isFetching, setIsFetching] = useState(false);
  const observerTarget = useRef<HTMLDivElement>(null);

  const handleLoadMore = useCallback(async () => {
    if (isFetching || isLoading || !hasMore) return;

    setIsFetching(true);
    try {
      await onLoadMore();
    } catch (error) {
      console.error('Error loading more items:', error);
    } finally {
      setIsFetching(false);
    }
  }, [isFetching, isLoading, hasMore, onLoadMore]);

  useEffect(() => {
    const target = observerTarget.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const firstEntry = entries[0];
        if (firstEntry.isIntersecting && hasMore && !isLoading && !isFetching) {
          handleLoadMore();
        }
      },
      {
        threshold,
        rootMargin,
      }
    );

    observer.observe(target);

    return () => {
      if (target) {
        observer.unobserve(target);
      }
    };
  }, [threshold, rootMargin, hasMore, isLoading, isFetching, handleLoadMore]);

  return {
    observerTarget,
    isFetching: isFetching || isLoading,
  };
}

export default useInfiniteScroll;
