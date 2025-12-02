import React from 'react';
import { SearchContainer } from '../Styles/SearchStyles.styles';
import SearchInput from './SearchInput';
import ResultsContainerComponent from './ResultsContainer';
import ResultAvatar from './ResultAvatar';
import { useSearchLogic } from '../Hooks/useSearchLogic';

export interface SearchResult {
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

/**
 * GlobalSearch - Multi-type global search component
 *
 * Searches across:
 * - Tracks (title, artist)
 * - Albums (title, artist)
 * - Artists (name)
 *
 * Features:
 * - 300ms debounced search
 * - Results grouped by type
 * - Type-specific avatars (album art, artist initials)
 * - Empty state handling
 * - Keyboard-friendly result selection
 */
export const GlobalSearch: React.FC<GlobalSearchProps> = ({ onResultClick, onClose }) => {
  const {
    query,
    setQuery,
    results,
    loading,
    showResults,
    handleResultClick,
    handleClear,
    groupedResults
  } = useSearchLogic(onResultClick);

  const getAvatar = (result: SearchResult) => (
    <ResultAvatar result={result} />
  );

  return (
    <SearchContainer>
      <SearchInput
        query={query}
        loading={loading}
        onQueryChange={setQuery}
        onClear={handleClear}
      />

      <ResultsContainerComponent
        visible={showResults}
        results={results}
        loading={loading}
        query={query}
        groupedResults={groupedResults}
        getAvatar={getAvatar}
        onResultClick={handleResultClick}
      />
    </SearchContainer>
  );
};

export default GlobalSearch;
