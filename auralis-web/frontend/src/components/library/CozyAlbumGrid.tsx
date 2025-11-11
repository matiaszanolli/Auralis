/**
 * CozyAlbumGrid Component
 *
 * Displays albums in a responsive grid layout with album artwork,
 * following the Auralis dark theme aesthetic with aurora gradients.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Grid,
  Typography,
  Skeleton,
} from '@mui/material';
import { colors } from '../../theme/auralisTheme';
import { AlbumCard } from '../album/AlbumCard';

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

const EmptyState = ({ children }: { children: React.ReactNode }) => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '400px',
      color: colors.text.disabled,
      textAlign: 'center',
      padding: '40px',
    }}
  >
    {children}
  </Box>
);

const EmptyStateText = ({ children }: { children: React.ReactNode }) => (
  <Typography
    sx={{
      fontSize: '18px',
      fontWeight: 500,
      marginBottom: '8px',
      color: colors.text.secondary,
    }}
  >
    {children}
  </Typography>
);

const EmptyStateSubtext = ({ children }: { children: React.ReactNode }) => (
  <Typography
    sx={{
      fontSize: '14px',
      color: colors.text.disabled,
    }}
  >
    {children}
  </Typography>
);

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

  // Ref to track if we're currently fetching (prevents duplicate requests)
  const isFetchingRef = useRef(false);

  const fetchAlbums = useCallback(async (resetPagination = false, overrideOffset?: number) => {
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
      const currentOffset = resetPagination ? 0 : (overrideOffset !== undefined ? overrideOffset : offset);

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
        // Deduplicate albums by ID to prevent duplicate key warnings
        const newAlbums = data.albums || [];
        setAlbums(prev => {
          const existingIds = new Set(prev.map(a => a.id));
          const uniqueNewAlbums = newAlbums.filter(a => !existingIds.has(a.id));
          return [...prev, ...uniqueNewAlbums];
        });
      }

      console.log(`Loaded ${data.albums?.length || 0} albums, ${currentOffset + (data.albums?.length || 0)}/${data.total || 0}`);
    } catch (err) {
      console.error('Error fetching albums:', err);
      setError(err instanceof Error ? err.message : 'Failed to load albums');
    } finally {
      setLoading(false);
      setIsLoadingMore(false);
    }
  }, [offset]);

  const loadMore = async () => {
    if (isLoadingMore || !hasMore) {
      return;
    }

    const limit = 50;
    const newOffset = offset + limit;
    setOffset(newOffset);
    await fetchAlbums(false, newOffset);
  };

  const handleAlbumClick = (albumId: number) => {
    if (onAlbumClick) {
      onAlbumClick(albumId);
    }
  };

  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  // Initial fetch on component mount (once only)
  useEffect(() => {
    fetchAlbums(true);
  }, []);

  // Load more albums when we're running low on content
  useEffect(() => {
    // Check if we need to load more content
    // Load when we have content but are showing less than 60% of total available
    if (albums.length > 0 &&
        albums.length < totalAlbums &&
        !isLoadingMore &&
        hasMore &&
        albums.length < 150) {  // Load more if we have less than 150 albums loaded

      const limit = 50;
      const newOffset = albums.length;  // Use actual loaded count as offset

      isFetchingRef.current = true;
      fetchAlbums(false, newOffset).finally(() => {
        isFetchingRef.current = false;
      });
    }
  }, [albums.length, totalAlbums, isLoadingMore, hasMore, fetchAlbums]);

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
      <EmptyState>
        <EmptyStateText>Error Loading Albums</EmptyStateText>
        <EmptyStateSubtext>{error}</EmptyStateSubtext>
      </EmptyState>
    );
  }

  if (albums.length === 0) {
    return (
      <EmptyState>
        <EmptyStateText>No Albums Yet</EmptyStateText>
        <EmptyStateSubtext>
          Your album library will appear here once you scan your music folder
        </EmptyStateSubtext>
      </EmptyState>
    );
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        p: 3
      }}
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

      {/* Loading indicator */}
      {isLoadingMore && (
        <Box
          sx={{
            height: '100px',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            p: 2
          }}
        >
          <Box
            sx={{
              width: 20,
              height: 20,
              border: '2px solid',
              borderColor: 'primary.main',
              borderRightColor: 'transparent',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              '@keyframes spin': {
                '0%': { transform: 'rotate(0deg)' },
                '100%': { transform: 'rotate(360deg)' }
              }
            }}
          />
          <Typography variant="body2" color="text.secondary" sx={{ ml: 2 }}>
            Loading more albums... ({albums.length}/{totalAlbums})
          </Typography>
        </Box>
      )}

      {/* End of list indicator */}
      {!hasMore && albums.length > 0 && (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Showing all {totalAlbums} albums
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default CozyAlbumGrid;
