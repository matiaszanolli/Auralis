/**
 * CozyAlbumGrid Component
 *
 * Displays albums in a responsive grid layout with album artwork,
 * following the Auralis dark theme aesthetic with aurora gradients.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Grid,
  Typography,
  Skeleton,
} from '@mui/material';
import { AlbumCard } from '../album/AlbumCard';
import { EmptyState } from '../../shared/ui/feedback';
import { GridContainer } from '../Styles/Grid.styles';
import InfiniteScrollTrigger from './InfiniteScrollTrigger';
import EndOfListIndicator from './EndOfListIndicator';
import GridLoadingState from './GridLoadingState';

interface Album {
  id: number;
  title: string;
  artist: string;
  track_count: number;
  total_duration: number;
  year?: number;
  artwork_path?: string;
}

interface CozyAlbumGridProps {
  onAlbumClick?: (albumId: number) => void;
}

export const CozyAlbumGrid: React.FC<CozyAlbumGridProps> = ({ onAlbumClick }) => {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [totalAlbums, setTotalAlbums] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Ref for scroll container
  const containerRef = useRef<HTMLDivElement>(null);

  // Ref for load more trigger element
  const loadMoreTriggerRef = useRef<HTMLDivElement>(null);

  // Ref to track if we're currently fetching (prevents duplicate requests)
  const isFetchingRef = useRef(false);

  const fetchAlbums = async (resetPagination = false) => {
    if (resetPagination) {
      setLoading(true);
      setOffset(0);
      setAlbums([]);
    } else {
      setIsLoadingMore(true);
    }

    setError(null);

    try {
      const limit = 50;
      const currentOffset = resetPagination ? 0 : offset;

      const response = await fetch(`/api/albums?limit=${limit}&offset=${currentOffset}`);
      if (!response.ok) {
        throw new Error('Failed to fetch albums');
      }

      const data = await response.json();

      // Update state with pagination info
      setHasMore(data.has_more || false);
      setTotalAlbums(data.total || 0);

      if (resetPagination) {
        setAlbums(data.albums || []);
      } else {
        const newAlbums = data.albums || [];
        setAlbums(prev => {
          const existingIds = new Set(prev.map((a: Album) => a.id));
          return [...prev, ...newAlbums.filter((a: Album) => !existingIds.has(a.id))];
        });
      }
    } catch (err) {
      console.error('Error fetching albums:', err);
      setError(err instanceof Error ? err.message : 'Failed to load albums');
    } finally {
      setLoading(false);
      setIsLoadingMore(false);
    }
  };

  const loadMore = async () => {
    if (isLoadingMore || !hasMore) {
      return;
    }

    const limit = 50;
    const newOffset = offset + limit;
    setOffset(newOffset);
    await fetchAlbums(false);
  };

  const handleAlbumClick = (albumId: number) => {
    if (onAlbumClick) {
      onAlbumClick(albumId);
    }
  };

  useEffect(() => {
    fetchAlbums(true);
  }, []);

  // Infinite scroll with scroll event checking sentinel element visibility
  useEffect(() => {
    const handleScroll = () => {
      if (!hasMore || isLoadingMore || loading) return;

      const triggerElement = loadMoreTriggerRef.current;
      if (!triggerElement) return;

      const rect = triggerElement.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const isNearViewport = rect.top < viewportHeight + 2000;

      if (isNearViewport) {
        loadMore();
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
  }, [hasMore, isLoadingMore, loading, offset, albums.length]);

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Grid container spacing={3}>
          {[...Array(12)].map((_, index) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={index}>
              <Box>
                <Skeleton
                  variant="rectangular"
                  width="100%"
                  height={200}
                  sx={{ borderRadius: '8px', marginBottom: '12px' }}
                />
                <Skeleton variant="text" width="80%" />
                <Skeleton variant="text" width="60%" />
                <Skeleton variant="text" width="40%" />
              </Box>
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (error) {
    return (
      <EmptyState
        title="Error Loading Albums"
        description={error}
      />
    );
  }

  if (albums.length === 0) {
    return (
      <EmptyState
        title="No Albums Yet"
        description="Your album library will appear here once you scan your music folder"
      />
    );
  }

  return (
    <GridContainer
      ref={containerRef}
    >
      <Grid container spacing={3}>
        {albums.map((album) => (
          <Grid item xs={12} sm={6} md={4} lg={3} key={album.id}>
            <AlbumCard
              albumId={album.id}
              title={album.title}
              artist={album.artist}
              trackCount={album.track_count}
              duration={album.total_duration}
              year={album.year}
              hasArtwork={!!album.artwork_path}
              onClick={() => handleAlbumClick(album.id)}
            />
          </Grid>
        ))}
      </Grid>

      {/* Load more trigger - invisible sentinel element */}
      {hasMore && <InfiniteScrollTrigger ref={loadMoreTriggerRef} />}

      {/* Loading indicator */}
      {isLoadingMore && (
        <GridLoadingState current={albums.length} total={totalAlbums} itemType="albums" />
      )}

      {/* End of list indicator */}
      {!hasMore && albums.length > 0 && (
        <EndOfListIndicator count={totalAlbums} itemType="albums" />
      )}
    </GridContainer>
  );
};

export default CozyAlbumGrid;
