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

  // Ref for infinite scroll observer
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchArtists(true);
  }, []);

  // Infinite scroll with Intersection Observer
  useEffect(() => {
    if (!loadMoreRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoadingMore && !loading) {
          loadMore();
        }
      },
      { threshold: 0.5 }
    );

    observer.observe(loadMoreRef.current);

    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, loading]);

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

      const response = await fetch(`http://localhost:8765/api/artists?limit=${limit}&offset=${currentOffset}`);
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
        setArtists(prev => [...prev, ...(data.artists || [])]);
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
    <ListContainer>
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
                <StyledListItemButton onClick={() => handleArtistClick(artist)}>
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

      {/* Infinite scroll loading indicator */}
      {hasMore && !loading && (
        <Box
          ref={loadMoreRef}
          sx={{
            p: 3,
            textAlign: 'center',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2
          }}
        >
          {isLoadingMore && (
            <>
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
              <Typography variant="body2" color="text.secondary">
                Loading more artists... ({artists.length}/{totalArtists})
              </Typography>
            </>
          )}
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
    </ListContainer>
  );
};

export default CozyArtistList;
