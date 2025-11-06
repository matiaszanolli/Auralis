/**
 * CozyArtistList Component
 *
 * Displays artists in a clean list layout with album counts and track information.
 * Follows the Auralis dark theme aesthetic.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Typography,
  styled,
  Skeleton,
  Avatar,
} from '@mui/material';
import { Person, MusicNote } from '@mui/icons-material';
import { colors } from '../../theme/auralisTheme';
import { useContextMenu, ContextMenu, getArtistContextActions } from '../shared/ContextMenu';
import { useToast } from '../shared/Toast';

interface Artist {
  id: number;
  name: string;
  album_count?: number;
  track_count?: number;
}

interface CozyArtistListProps {
  onArtistClick?: (artistId: number, artistName: string) => void;
}

const ListContainer = styled(Box)({
  padding: '24px',
  width: '100%',
});

const StyledListItem = styled(ListItem)({
  padding: 0,
  marginBottom: '8px',
});

const StyledListItemButton = styled(ListItemButton)({
  borderRadius: '12px',
  padding: '16px 20px',
  transition: 'all 0.3s ease',
  border: '1px solid transparent',

  '&:hover': {
    backgroundColor: 'rgba(102, 126, 234, 0.08)',
    border: '1px solid rgba(102, 126, 234, 0.3)',
    transform: 'translateX(4px)',

    '& .artist-name': {
      color: '#667eea',
    },
  },
});

const ArtistAvatar = styled(Avatar)({
  width: 56,
  height: 56,
  marginRight: '20px',
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  fontSize: '24px',
});

const ArtistName = styled(Typography)({
  fontSize: '18px',
  fontWeight: 600,
  color: colors.text.primary,
  transition: 'color 0.2s ease',
});

const ArtistInfo = styled(Typography)({
  fontSize: '14px',
  color: colors.text.secondary,
  marginTop: '4px',
});

const EmptyState = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  minHeight: '400px',
  color: colors.text.disabled,
  textAlign: 'center',
  padding: '40px',
});

const EmptyStateText = styled(Typography)({
  fontSize: '18px',
  fontWeight: 500,
  marginBottom: '8px',
  color: colors.text.secondary,
});

const EmptyStateSubtext = styled(Typography)({
  fontSize: '14px',
  color: colors.text.disabled,
});

const SectionHeader = styled(Box)({
  marginBottom: '24px',
  paddingBottom: '16px',
  borderBottom: `1px solid ${colors.background.hover}`,
});

const AlphabetDivider = styled(Typography)({
  fontSize: '14px',
  fontWeight: 700,
  color: '#667eea',
  textTransform: 'uppercase',
  letterSpacing: '1px',
  marginTop: '32px',
  marginBottom: '12px',
  paddingLeft: '8px',
});

export const CozyArtistList: React.FC<CozyArtistListProps> = ({ onArtistClick }) => {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [totalArtists, setTotalArtists] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [contextMenuArtist, setContextMenuArtist] = useState<Artist | null>(null);

  // Ref for scroll container
  const containerRef = useRef<HTMLDivElement>(null);

  // Ref for load more trigger element
  const loadMoreTriggerRef = useRef<HTMLDivElement>(null);

  // Context menu state
  const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();
  const { success, info } = useToast();

  useEffect(() => {
    fetchArtists(true);
  }, []);

  // Infinite scroll with scroll event checking sentinel element visibility
  useEffect(() => {
    console.log('CozyArtistList: Setting up scroll listener', {
      hasMore,
      isLoadingMore,
      loading,
      offset,
      artistsCount: artists.length
    });

    const handleScroll = () => {
      // Log all guard conditions
      console.log('CozyArtistList: handleScroll called', {
        hasMore,
        isLoadingMore,
        loading,
        triggerExists: !!loadMoreTriggerRef.current,
        containerExists: !!containerRef.current
      });

      if (!hasMore || isLoadingMore || loading) {
        console.log('CozyArtistList: Guard condition blocked scroll', {
          hasMore,
          isLoadingMore,
          loading
        });
        return;
      }

      // Check if load more trigger element is visible in viewport
      const triggerElement = loadMoreTriggerRef.current;
      if (!triggerElement) {
        console.log('CozyArtistList: Trigger element not found');
        return;
      }

      const rect = triggerElement.getBoundingClientRect();
      const viewportHeight = window.innerHeight;

      console.log('CozyArtistList: Checking trigger visibility', {
        triggerTop: rect.top,
        triggerBottom: rect.bottom,
        viewportHeight,
        isNearViewport: rect.top < viewportHeight + 2000
      });

      // Trigger load when sentinel element is within 2000px of viewport
      // This ensures loading starts before user scrolls all the way to the end
      const isNearViewport = rect.top < viewportHeight + 2000;

      if (isNearViewport) {
        console.log('CozyArtistList: Load trigger visible, loading more', {
          triggerTop: rect.top,
          viewportHeight,
          hasMore,
          isLoadingMore
        });
        loadMore();
      }
    };

    // Find scrollable parent and attach listener
    let scrollableParent = containerRef.current?.parentElement;
    console.log('CozyArtistList: Starting parent search', {
      containerExists: !!containerRef.current,
      parentExists: !!scrollableParent
    });

    while (scrollableParent) {
      const overflowY = window.getComputedStyle(scrollableParent).overflowY;
      console.log('CozyArtistList: Checking parent', {
        tagName: scrollableParent.tagName,
        className: scrollableParent.className,
        overflowY
      });

      if (overflowY === 'auto' || overflowY === 'scroll') {
        break;
      }
      scrollableParent = scrollableParent.parentElement;
    }

    if (scrollableParent) {
      console.log('CozyArtistList: Attached scroll listener to', {
        tagName: scrollableParent.tagName,
        className: scrollableParent.className
      });
      scrollableParent.addEventListener('scroll', handleScroll);
      // Also check on mount in case content is already visible
      handleScroll();
      return () => {
        console.log('CozyArtistList: Removing scroll listener');
        scrollableParent.removeEventListener('scroll', handleScroll);
      };
    } else {
      console.warn('CozyArtistList: No scrollable parent found!');
    }
  }, [hasMore, isLoadingMore, loading, offset, artists.length]);

  const fetchArtists = async (resetPagination = false) => {
    if (resetPagination) {
      setLoading(true);
      setOffset(0);
      setArtists([]);
    } else {
      setIsLoadingMore(true);
    }

    setError(null);

    try {
      const limit = 50;
      const currentOffset = resetPagination ? 0 : offset;

      const response = await fetch(`/api/artists?limit=${limit}&offset=${currentOffset}`);
      if (!response.ok) {
        throw new Error('Failed to fetch artists');
      }

      const data = await response.json();

      // Update state with pagination info
      setHasMore(data.has_more || false);
      setTotalArtists(data.total || 0);

      if (resetPagination) {
        setArtists(data.artists || []);
      } else {
        // Deduplicate artists by ID to prevent duplicate key warnings
        const newArtists = data.artists || [];
        setArtists(prev => {
          const existingIds = new Set(prev.map(a => a.id));
          const uniqueNewArtists = newArtists.filter(a => !existingIds.has(a.id));
          return [...prev, ...uniqueNewArtists];
        });
      }

      console.log(`Loaded ${data.artists?.length || 0} artists, ${currentOffset + (data.artists?.length || 0)}/${data.total || 0}`);
    } catch (err) {
      console.error('Error fetching artists:', err);
      setError(err instanceof Error ? err.message : 'Failed to load artists');
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
    await fetchArtists(false);
  };

  const handleArtistClick = (artist: Artist) => {
    if (onArtistClick) {
      onArtistClick(artist.id, artist.name);
    }
  };

  const handleContextMenuOpen = (e: React.MouseEvent, artist: Artist) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenuArtist(artist);
    handleContextMenu(e);
  };

  const handleContextMenuClose = () => {
    setContextMenuArtist(null);
    handleCloseContextMenu();
  };

  // Context menu actions
  const contextActions = contextMenuArtist
    ? getArtistContextActions(contextMenuArtist.id, {
        onPlayAll: () => {
          success(`Playing all songs by ${contextMenuArtist.name}`);
          // TODO: Implement play all artist tracks
        },
        onAddToQueue: () => {
          success(`Added ${contextMenuArtist.name} to queue`);
          // TODO: Implement add artist to queue
        },
        onShowAlbums: () => {
          info(`Showing albums by ${contextMenuArtist.name}`);
          if (onArtistClick) {
            onArtistClick(contextMenuArtist.id, contextMenuArtist.name);
          }
        },
        onShowInfo: () => {
          info(`Artist: ${contextMenuArtist.name}\n${contextMenuArtist.album_count} albums • ${contextMenuArtist.track_count} tracks`);
          // TODO: Show artist info modal
        },
      })
    : [];

  const getArtistInitial = (name: string): string => {
    return name.charAt(0).toUpperCase();
  };

  // Group artists by first letter
  const groupedArtists = artists.reduce((acc, artist) => {
    const initial = getArtistInitial(artist.name);
    if (!acc[initial]) {
      acc[initial] = [];
    }
    acc[initial].push(artist);
    return acc;
  }, {} as Record<string, Artist[]>);

  const sortedLetters = Object.keys(groupedArtists).sort();

  if (loading) {
    return (
      <ListContainer>
        <List>
          {[...Array(15)].map((_, index) => (
            <StyledListItem key={index}>
              <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', padding: '16px 20px' }}>
                <Skeleton variant="circular" width={56} height={56} sx={{ marginRight: '20px' }} />
                <Box sx={{ flex: 1 }}>
                  <Skeleton variant="text" width="30%" height={24} />
                  <Skeleton variant="text" width="50%" height={20} sx={{ marginTop: '8px' }} />
                </Box>
              </Box>
            </StyledListItem>
          ))}
        </List>
      </ListContainer>
    );
  }

  if (error) {
    return (
      <EmptyState>
        <EmptyStateText>Error Loading Artists</EmptyStateText>
        <EmptyStateSubtext>{error}</EmptyStateSubtext>
      </EmptyState>
    );
  }

  if (artists.length === 0) {
    return (
      <EmptyState>
        <Person sx={{ fontSize: 64, marginBottom: 2, opacity: 0.3 }} />
        <EmptyStateText>No Artists Yet</EmptyStateText>
        <EmptyStateSubtext>
          Your artist library will appear here once you scan your music folder
        </EmptyStateSubtext>
      </EmptyState>
    );
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        padding: '24px',
        width: '100%'
      }}
    >
      <SectionHeader>
        <Typography variant="body2" color="text.secondary">
          {artists.length} {artists.length !== totalArtists ? `of ${totalArtists}` : ''} artists in your library
        </Typography>
      </SectionHeader>

      <List>
        {sortedLetters.map((letter) => (
          <Box key={letter}>
            <AlphabetDivider>{letter}</AlphabetDivider>
            {groupedArtists[letter].map((artist) => (
              <StyledListItem key={artist.id}>
                <StyledListItemButton
                  onClick={() => handleArtistClick(artist)}
                  onContextMenu={(e) => handleContextMenuOpen(e, artist)}
                >
                  <ArtistAvatar>
                    {getArtistInitial(artist.name)}
                  </ArtistAvatar>
                  <ListItemText
                    primary={
                      <ArtistName className="artist-name">
                        {artist.name}
                      </ArtistName>
                    }
                    secondary={
                      <ArtistInfo>
                        {artist.album_count
                          ? `${artist.album_count} ${artist.album_count === 1 ? 'album' : 'albums'}`
                          : ''}
                        {artist.album_count && artist.track_count ? ' • ' : ''}
                        {artist.track_count
                          ? `${artist.track_count} ${artist.track_count === 1 ? 'track' : 'tracks'}`
                          : ''}
                      </ArtistInfo>
                    }
                  />
                </StyledListItemButton>
              </StyledListItem>
            ))}
          </Box>
        ))}
      </List>

      {/* Load more trigger - invisible sentinel element */}
      {hasMore && (
        <Box
          ref={loadMoreTriggerRef}
          sx={{
            height: '1px',
            width: '100%',
          }}
        />
      )}

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
            Loading more artists... ({artists.length}/{totalArtists})
          </Typography>
        </Box>
      )}

      {/* End of list indicator */}
      {!hasMore && artists.length > 0 && (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Showing all {totalArtists} artists
          </Typography>
        </Box>
      )}

      {/* Context menu */}
      <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={handleContextMenuClose}
        actions={contextActions}
      />
    </Box>
  );
};

export default CozyArtistList;
