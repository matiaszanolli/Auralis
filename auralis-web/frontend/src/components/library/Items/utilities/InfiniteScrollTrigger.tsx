/**
 * InfiniteScrollTrigger Component
 *
 * Invisible sentinel element used to detect when user has scrolled near
 * the bottom of content. Integrates with Intersection Observer API
 * to trigger pagination/infinite scroll loading.
 *
 * Used by: TrackListView (grid view), CozyAlbumGrid
 *
 * Usage:
 * ```tsx
 * const triggerRef = useRef<HTMLDivElement>(null);
 *
 * useEffect(() => {
 *   const observer = new IntersectionObserver(
 *     (entries) => {
 *       if (entries[0].isIntersecting && hasMore && !isLoadingMore) {
 *         onLoadMore();
 *       }
 *     },
 *     { threshold: 0.1, rootMargin: '100px' }
 *   );
 *   observer.observe(triggerRef.current);
 *   return () => observer.disconnect();
 * }, [hasMore, isLoadingMore, onLoadMore]);
 *
 * return (
 *   <InfiniteScrollTrigger ref={triggerRef}>
 *     {isLoadingMore && <LoadingSpinner />}
 *   </InfiniteScrollTrigger>
 * );
 * ```
 */

import { ReactNode, Ref, forwardRef } from 'react';
import { InfiniteScrollTrigger as StyledTrigger } from '@/components/library/Styles/Grid.styles';

interface InfiniteScrollTriggerProps {
  ref?: Ref<HTMLDivElement>;
  children?: ReactNode;
}

export const InfiniteScrollTrigger = forwardRef<HTMLDivElement, InfiniteScrollTriggerProps>(
  ({ children }, ref) => (
    <StyledTrigger ref={ref}>
      {children}
    </StyledTrigger>
  )
);

InfiniteScrollTrigger.displayName = 'InfiniteScrollTrigger';

export default InfiniteScrollTrigger;
