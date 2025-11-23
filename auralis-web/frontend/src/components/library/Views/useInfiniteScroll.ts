import { useEffect } from 'react';

export interface UseInfiniteScrollProps {
  hasMore: boolean;
  isLoadingMore: boolean;
  isLoading: boolean;
  onLoadMore: () => void;
  loadMoreRef: React.RefObject<HTMLDivElement>;
}

/**
 * useInfiniteScroll - Intersection Observer for infinite scroll
 *
 * Automatically triggers onLoadMore when user scrolls near the end.
 * Includes debouncing to prevent multiple simultaneous load requests.
 */
export const useInfiniteScroll = ({
  hasMore,
  isLoadingMore,
  isLoading,
  onLoadMore,
  loadMoreRef,
}: UseInfiniteScrollProps) => {
  useEffect(() => {
    if (!loadMoreRef.current) return;

    // Debounce flag to prevent multiple simultaneous loads
    let isObserverLoading = false;

    const observer = new IntersectionObserver(
      (entries) => {
        if (
          entries[0].isIntersecting &&
          hasMore &&
          !isLoadingMore &&
          !isLoading &&
          !isObserverLoading
        ) {
          isObserverLoading = true;
          onLoadMore();
          // Reset after a delay to prevent rapid refiring
          setTimeout(() => {
            isObserverLoading = false;
          }, 500);
        }
      },
      { threshold: 0.1, rootMargin: '100px' } // Load when 100px away from trigger
    );

    observer.observe(loadMoreRef.current);

    return () => {
      observer.disconnect();
      isObserverLoading = false;
    };
  }, [hasMore, isLoadingMore, isLoading, onLoadMore]);
};
