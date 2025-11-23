import React from 'react';
import { Box, List, Typography } from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { ResultsContainer } from './SearchStyles.styles';
import ResultGroup from './ResultGroup';

interface SearchResult {
  type: 'track' | 'album' | 'artist';
  id: number;
  title: string;
  subtitle?: string;
  albumId?: number;
}

interface GroupedResults {
  tracks: SearchResult[];
  albums: SearchResult[];
  artists: SearchResult[];
}

interface ResultsContainerComponentProps {
  visible: boolean;
  results: SearchResult[];
  loading: boolean;
  query: string;
  groupedResults: GroupedResults;
  getAvatar: (result: SearchResult) => React.ReactNode;
  onResultClick: (result: SearchResult) => void;
}

/**
 * ResultsContainer - Renders search results dropdown with empty state
 *
 * Displays:
 * - Grouped results (tracks, albums, artists)
 * - Empty state message when no results found
 * - Loading state handling
 *
 * Manages visibility and rendering of results
 */
export const ResultsContainerComponent: React.FC<ResultsContainerComponentProps> = ({
  visible,
  results,
  loading,
  query,
  groupedResults,
  getAvatar,
  onResultClick
}) => {
  if (!visible) {
    return null;
  }

  if (results.length > 0) {
    return (
      <ResultsContainer elevation={8}>
        <List sx={{ py: 1 }}>
          <ResultGroup
            title="Tracks"
            results={groupedResults.tracks}
            showDivider={false}
            getAvatar={getAvatar}
            chipLabel="Track"
            chipClass="track"
            onResultClick={onResultClick}
          />

          <ResultGroup
            title="Albums"
            results={groupedResults.albums}
            showDivider={groupedResults.tracks.length > 0}
            getAvatar={getAvatar}
            chipLabel="Album"
            chipClass="album"
            onResultClick={onResultClick}
          />

          <ResultGroup
            title="Artists"
            results={groupedResults.artists}
            showDivider={groupedResults.tracks.length > 0 || groupedResults.albums.length > 0}
            getAvatar={getAvatar}
            chipLabel="Artist"
            chipClass="artist"
            onResultClick={onResultClick}
          />
        </List>
      </ResultsContainer>
    );
  }

  // Empty state
  if (!loading && query.length >= 2) {
    return (
      <ResultsContainer elevation={8}>
        <Box sx={{ padding: 4, textAlign: 'center' }}>
          <SearchIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography color="text.secondary">
            No results found for "{query}"
          </Typography>
        </Box>
      </ResultsContainer>
    );
  }

  return null;
};

export default ResultsContainerComponent;
