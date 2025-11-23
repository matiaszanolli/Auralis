/**
 * useAlbumGridScroll Hook
 *
 * Manages infinite scroll logic with sentinel element detection
 */

import { useEffect, useRef } from 'react';

interface UseAlbumGridScrollProps {
  hasMore: boolean;
  isLoadingMore: boolean;
  loading: boolean;
  offset: number;
  albumsLength: number;
  onLoadMore: () => void;
}

export const useAlbumGridScroll = ({
  hasMore,
  isLoadingMore,
  loading,
  offset,
  albumsLength,
  onLoadMore,
}: UseAlbumGridScrollProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const loadMoreTriggerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleScroll = () => {
      if (!hasMore || isLoadingMore || loading) return;

      const triggerElement = loadMoreTriggerRef.current;
      if (!triggerElement) return;

      const rect = triggerElement.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const isNearViewport = rect.top < viewportHeight + 2000;

      if (isNearViewport) {
        onLoadMore();
      }
    };

    // Find scrollable parent and attach listener
    let scrollableParent = containerRef.current?.parentElement;
    while (scrollableParent) {
      const overflowY = window.getComputedStyle(scrollableParent).overflowY;
      if (overflowY === 'auto' || overflowY === 'scroll') break;
      scrollableParent = scrollableParent.parentElement;
    }

    if (scrollableParent) {
      scrollableParent.addEventListener('scroll', handleScroll);
      handleScroll();
      return () => {
        scrollableParent.removeEventListener('scroll', handleScroll);
      };
    }
  }, [hasMore, isLoadingMore, loading, offset, albumsLength, onLoadMore]);

  return {
    containerRef,
    loadMoreTriggerRef,
  };
};
