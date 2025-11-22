import React, { useState, useEffect } from 'react';
import {
  InputAdornment,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Typography,
  Divider,
  CircularProgress,
  Box
} from '@mui/material';
import {
  Search as SearchIcon,
  Album as AlbumIcon,
  Person as PersonIcon,
  MusicNote as MusicNoteIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import {
  SearchContainer,
  SearchField,
  ResultsContainer,
  CategoryHeader,
  StyledListItemButton,
  ResultTitle,
  ResultSubtitle,
  TypeChip
} from './SearchStyles.styles';
import AlbumArt from '../album/AlbumArt';

interface SearchResult {
  type: 'track' | 'album' | 'artist';
  id: number;
  title: string;
  subtitle?: string;
  albumId?: number;
}

interface GlobalSearchProps {
  onResultClick?: (result: SearchResult) => void;
  onClose?: () => void;
}

export const GlobalSearch: React.FC<GlobalSearchProps> = ({ onResultClick, onClose }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);

  // Debounced search
  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      setShowResults(false);
      return;
    }

    const timeoutId = setTimeout(() => {
      performSearch(query);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [query]);

  const performSearch = async (searchQuery: string) => {
    setLoading(true);
    const allResults: SearchResult[] = [];

    try {
      // Search tracks
      const tracksResponse = await fetch(
        `/api/library/tracks?limit=100`
      );
      if (tracksResponse.ok) {
        const tracksData = await tracksResponse.json();
        const matchingTracks = tracksData.tracks
          .filter((track: any) =>
            track.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            track.artist.toLowerCase().includes(searchQuery.toLowerCase())
          )
          .slice(0, 5)
          .map((track: any) => ({
            type: 'track' as const,
            id: track.id,
            title: track.title,
            subtitle: `${track.artist} • ${track.album}`,
            albumId: track.album_id
          }));
        allResults.push(...matchingTracks);
      }

      // Search albums
      const albumsResponse = await fetch('/api/library/albums');
      if (albumsResponse.ok) {
        const albumsData = await albumsResponse.json();
        const matchingAlbums = albumsData.albums
          .filter((album: any) =>
            album.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            album.artist.toLowerCase().includes(searchQuery.toLowerCase())
          )
          .slice(0, 5)
          .map((album: any) => ({
            type: 'album' as const,
            id: album.id,
            title: album.title,
            subtitle: album.artist,
            albumId: album.id
          }));
        allResults.push(...matchingAlbums);
      }

      // Search artists
      const artistsResponse = await fetch('/api/library/artists');
      if (artistsResponse.ok) {
        const artistsData = await artistsResponse.json();
        const matchingArtists = artistsData.artists
          .filter((artist: any) =>
            artist.name.toLowerCase().includes(searchQuery.toLowerCase())
          )
          .slice(0, 5)
          .map((artist: any) => ({
            type: 'artist' as const,
            id: artist.id,
            title: artist.name,
            subtitle: `${artist.album_count || 0} albums • ${artist.track_count || 0} tracks`
          }));
        allResults.push(...matchingArtists);
      }

      setResults(allResults);
      setShowResults(true);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleResultClick = (result: SearchResult) => {
    if (onResultClick) {
      onResultClick(result);
    }
    setQuery('');
    setShowResults(false);
  };

  const handleClear = () => {
    setQuery('');
    setResults([]);
    setShowResults(false);
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'track':
        return <MusicNoteIcon />;
      case 'album':
        return <AlbumIcon />;
      case 'artist':
        return <PersonIcon />;
      default:
        return <MusicNoteIcon />;
    }
  };

  const getAvatar = (result: SearchResult) => {
    if (result.type === 'album' || (result.type === 'track' && result.albumId)) {
      return (
        <AlbumArt
          albumId={result.albumId || result.id}
          size={40}
          borderRadius={4}
        />
      );
    }

    if (result.type === 'artist') {
      return (
        <Avatar
          sx={{
            width: 40,
            height: 40,
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            fontSize: '1rem',
            fontWeight: 'bold'
          }}
        >
          {result.title.charAt(0).toUpperCase()}
        </Avatar>
      );
    }

    return (
      <Avatar sx={{ width: 40, height: 40, bgcolor: 'rgba(102, 126, 234, 0.2)' }}>
        {getIcon(result.type)}
      </Avatar>
    );
  };

  // Group results by type
  const groupedResults = {
    tracks: results.filter(r => r.type === 'track'),
    albums: results.filter(r => r.type === 'album'),
    artists: results.filter(r => r.type === 'artist')
  };

  return (
    <SearchContainer>
      <SearchField
        fullWidth
        placeholder="Search tracks, albums, artists..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              {loading ? (
                <CircularProgress size={20} sx={{ color: '#667eea' }} />
              ) : (
                <SearchIcon sx={{ color: 'text.secondary' }} />
              )}
            </InputAdornment>
          ),
          endAdornment: query && (
            <InputAdornment position="end">
              <CloseIcon
                sx={{
                  cursor: 'pointer',
                  color: 'text.secondary',
                  '&:hover': { color: 'text.primary' }
                }}
                onClick={handleClear}
              />
            </InputAdornment>
          )
        }}
      />

      {showResults && results.length > 0 && (
        <ResultsContainer elevation={8}>
          <List sx={{ py: 1 }}>
            {groupedResults.tracks.length > 0 && (
              <>
                <CategoryHeader>Tracks</CategoryHeader>
                {groupedResults.tracks.map((result) => (
                  <StyledListItemButton
                    key={`${result.type}-${result.id}`}
                    onClick={() => handleResultClick(result)}
                  >
                    <ListItemAvatar>
                      {getAvatar(result)}
                    </ListItemAvatar>
                    <ListItemText
                      primary={
                        <ResultTitle className="result-title">
                          {result.title}
                        </ResultTitle>
                      }
                      secondary={<ResultSubtitle>{result.subtitle}</ResultSubtitle>}
                    />
                    <TypeChip label="Track" size="small" className="track" />
                  </StyledListItemButton>
                ))}
              </>
            )}

            {groupedResults.albums.length > 0 && (
              <>
                {groupedResults.tracks.length > 0 && <Divider sx={{ my: 1 }} />}
                <CategoryHeader>Albums</CategoryHeader>
                {groupedResults.albums.map((result) => (
                  <StyledListItemButton
                    key={`${result.type}-${result.id}`}
                    onClick={() => handleResultClick(result)}
                  >
                    <ListItemAvatar>
                      {getAvatar(result)}
                    </ListItemAvatar>
                    <ListItemText
                      primary={
                        <ResultTitle className="result-title">
                          {result.title}
                        </ResultTitle>
                      }
                      secondary={<ResultSubtitle>{result.subtitle}</ResultSubtitle>}
                    />
                    <TypeChip label="Album" size="small" className="album" />
                  </StyledListItemButton>
                ))}
              </>
            )}

            {groupedResults.artists.length > 0 && (
              <>
                {(groupedResults.tracks.length > 0 || groupedResults.albums.length > 0) && (
                  <Divider sx={{ my: 1 }} />
                )}
                <CategoryHeader>Artists</CategoryHeader>
                {groupedResults.artists.map((result) => (
                  <StyledListItemButton
                    key={`${result.type}-${result.id}`}
                    onClick={() => handleResultClick(result)}
                  >
                    <ListItemAvatar>
                      {getAvatar(result)}
                    </ListItemAvatar>
                    <ListItemText
                      primary={
                        <ResultTitle className="result-title">
                          {result.title}
                        </ResultTitle>
                      }
                      secondary={<ResultSubtitle>{result.subtitle}</ResultSubtitle>}
                    />
                    <TypeChip label="Artist" size="small" className="artist" />
                  </StyledListItemButton>
                ))}
              </>
            )}
          </List>
        </ResultsContainer>
      )}

      {showResults && results.length === 0 && !loading && query.length >= 2 && (
        <ResultsContainer elevation={8}>
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <SearchIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography color="text.secondary">
              No results found for "{query}"
            </Typography>
          </Box>
        </ResultsContainer>
      )}
    </SearchContainer>
  );
};

export default GlobalSearch;
