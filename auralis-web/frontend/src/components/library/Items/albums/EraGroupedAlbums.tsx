/**
 * Era-mode rendering, extracted from CozyAlbumGrid.tsx (#4456).
 *
 * Lists `EraSection`s (each internally virtualized) and drives
 * infinite-scroll loading from a sentinel at the bottom of the list.
 */

import { useEffect, useRef } from 'react';
import { tokens } from '@/design-system';
import { EraSection } from './EraSection';
import { groupAlbumsByEra } from '@/utils/eraGrouping';
import type { VirtualizedGridSharedProps } from './albumGridTypes';

interface EraGroupedAlbumsProps extends VirtualizedGridSharedProps {
  eraGroups: ReturnType<typeof groupAlbumsByEra<import('@/types/domain').Album>>;
}

export function EraGroupedAlbums({
  eraGroups,
  fingerprints,
  hasNextPage,
  onLoadMore,
  onAlbumClick,
  onAlbumHover,
  onAlbumHoverEnd,
}: EraGroupedAlbumsProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const target = sentinelRef.current;
    if (!target || !hasNextPage) return;
    if (typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) onLoadMore();
        }
      },
      { rootMargin: '400px' }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasNextPage, onLoadMore]);

  return (
    <>
      {eraGroups.map((eraGroup) => (
        <EraSection
          key={eraGroup.label}
          label={eraGroup.label}
          albums={eraGroup.albums}
          fingerprints={fingerprints}
          onAlbumClick={onAlbumClick}
          onAlbumHover={onAlbumHover}
          onAlbumHoverEnd={onAlbumHoverEnd}
        />
      ))}
      {hasNextPage && (
        <div
          ref={sentinelRef}
          style={{ padding: tokens.spacing.group, textAlign: 'center' }}
        >
          Loading more albums...
        </div>
      )}
    </>
  );
}
