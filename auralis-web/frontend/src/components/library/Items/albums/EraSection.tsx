/**
 * EraSection Component
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * Displays a group of albums from a specific era with a header.
 * Used to organize albums chronologically in the albums view.
 *
 * Design: Section header (era label) followed by horizontal album row.
 *
 * #3606: virtualizes the inner album grid via `useGridVirtualizer` so a single
 * era spanning hundreds of albums still keeps DOM `AlbumCard` count bounded.
 * Falls back to mapping every album when layout is unmeasurable (jsdom).
 */

import { useEffect, useRef, useState } from 'react';
import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import {
  computeColumnsPerRow,
  useContainerWidth,
  useGridVirtualizer,
} from '@/components/library/Items/utilities/useGridVirtualizer';

// Card visual height (200px square per token) + room for title/artist + row gap.
const ERA_ROW_HEIGHT = 304;
const ERA_COLUMN_WIDTH = 200; // matches `gridTemplateColumns: 'repeat(auto-fill, 200px)'`
const ERA_GAP_PX = 16; // tokens.spacing.group as px

interface Album {
  id: number;
  title: string;
  artist: string;
  artworkUrl?: string;
  trackCount?: number;
  totalDuration?: number;
  year?: number;
}

interface EraSectionProps {
  /** Era label (e.g., "1978 - 1982") */
  label: string;
  /** Albums in this era */
  albums: Album[];
  /** Map of album IDs to fingerprints */
  fingerprints: Map<number, AudioFingerprint | null>;
  /** Callback when an album is clicked */
  onAlbumClick?: (albumId: number) => void;
  /** Callback when an album is hovered */
  onAlbumHover?: (albumId: number, albumTitle?: string, albumArtist?: string) => void;
  /** Callback when album hover ends */
  onAlbumHoverEnd?: () => void;
}

/**
 * EraSection - Era header with virtualized album grid
 */
export const EraSection = ({
  label,
  albums,
  fingerprints,
  onAlbumClick,
  onAlbumHover,
  onAlbumHoverEnd,
}: EraSectionProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollElementRef = useRef<HTMLElement | null>(null);
  const [scrollReady, setScrollReady] = useState(false);

  useEffect(() => {
    scrollElementRef.current = document.getElementById('app-main-content-scroll');
    setScrollReady(scrollElementRef.current !== null);
  }, []);

  const containerWidth = useContainerWidth(containerRef);
  const columns = computeColumnsPerRow(containerWidth, ERA_COLUMN_WIDTH, ERA_GAP_PX);

  const virtualizer = useGridVirtualizer({
    itemCount: albums.length,
    columnsPerRow: columns,
    rowHeight: ERA_ROW_HEIGHT,
    getScrollElement: () => scrollElementRef.current,
    scrollMargin: containerRef.current?.offsetTop ?? 0,
  });

  // Don't render empty eras
  if (albums.length === 0) {
    return null;
  }

  const renderCard = (album: Album) => {
    const fingerprint = fingerprints.get(album.id) ?? undefined;
    return (
      <AlbumCard
        key={album.id}
        albumId={album.id}
        title={album.title}
        artist={album.artist}
        hasArtwork={!!album.artworkUrl}
        trackCount={album.trackCount}
        duration={album.totalDuration}
        year={album.year}
        fingerprint={fingerprint}
        onClick={onAlbumClick}
        onHoverEnter={onAlbumHover ? (id) => onAlbumHover(id, album.title, album.artist) : undefined}
        onHoverLeave={onAlbumHoverEnd}
      />
    );
  };

  const canVirtualize = scrollReady && containerWidth > 0;
  const virtualRows = virtualizer.getVirtualItems();

  return (
    <Box
      sx={{
        mb: tokens.spacing.xl,
      }}
    >
      {/* Era Header */}
      <Typography
        variant="h6"
        sx={{
          fontSize: tokens.typography.fontSize.lg,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.text.secondary,
          mb: tokens.spacing.md,
          pl: tokens.spacing.xs,
          // Subtle left border accent
          borderLeft: `3px solid ${tokens.colors.accent.primary}`,
          paddingLeft: tokens.spacing.md,
        }}
      >
        {label}
      </Typography>

      {/* Album Grid for this era */}
      <Box ref={containerRef}>
        {canVirtualize ? (
          <div
            style={{
              height: virtualizer.getTotalSize(),
              width: '100%',
              position: 'relative',
            }}
          >
            {virtualRows.map((virtualRow) => {
              const startIndex = virtualRow.index * columns;
              const rowAlbums = albums.slice(startIndex, startIndex + columns);
              return (
                <div
                  key={virtualRow.index}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    transform: `translateY(${virtualRow.start - (virtualizer.options.scrollMargin ?? 0)}px)`,
                    display: 'grid',
                    gridTemplateColumns: `repeat(auto-fill, ${ERA_COLUMN_WIDTH}px)`,
                    gap: tokens.spacing.group,
                  }}
                >
                  {rowAlbums.map(renderCard)}
                </div>
              );
            })}
          </div>
        ) : (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `repeat(auto-fill, ${ERA_COLUMN_WIDTH}px)`,
              gap: tokens.spacing.group,
            }}
          >
            {albums.map(renderCard)}
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default EraSection;
