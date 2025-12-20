import { useState, useEffect, useCallback, useRef, RefObject } from 'react';

interface UseInfiniteScrollOptions {
  /**
   * Optional external ref for the observer target element.
   * If not provided, an internal ref will be created and returned.
   */
  ref?: RefObject<HTMLDivElement>;
  /**
   * IntersectionObserver threshold (0-1). Default: 0.8
   */
  threshold?: number;
  /**
   * IntersectionObserver root margin. Default: '100px'
   */
  rootMargin?: string;
  /**
   * Callback to load more items. Must return a Promise.
   */
  onLoadMore: () => Promise<void>;
  /**
   * Whether there are more items to load.
   */
  hasMore: boolean;
  /**
   * Whether items are currently loading.
   */
  isLoading: boolean;
}

interface UseInfiniteScrollResult {
  /**
   * Ref to attach to the sentinel/trigger element.
   * Attach this to a div at the bottom of your scrollable content.
   */
  observerTarget: RefObject<HTMLDivElement>;
  /**
   * Whether a fetch is currently in progress (either from this hook or parent).
   */
  isFetching: boolean;
}

/**
 * Hook for infinite scroll functionality
 * Automatically loads more items when the user scrolls near the bottom
 *
 * @example
 * ```tsx
 * const { observerTarget, isFetching } = useInfiniteScroll({
 *   onLoadMore: fetchMore,
 *   hasMore,
 *   isLoading,
 * });
 *
 * return (
 *   <div>
 *     {items.map(item => <Item key={item.id} {...item} />)}
 *     <div ref={observerTarget} /> {/* Sentinel element *\/}
 *     {isFetching && <LoadingSpinner />}
 *   </div>
 * );
 * ```
 */
export function useInfiniteScroll({
  ref: externalRef,
  threshold = 0.8,
  rootMargin = '100px',
  onLoadMore,
  hasMore,
  isLoading,
}: UseInfiniteScrollOptions): UseInfiniteScrollResult {
  const [isFetching, setIsFetching] = useState(false);
  const internalRef = useRef<HTMLDivElement>(null);

  // Use external ref if provided, otherwise use internal
  const observerTarget = externalRef || internalRef;

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
