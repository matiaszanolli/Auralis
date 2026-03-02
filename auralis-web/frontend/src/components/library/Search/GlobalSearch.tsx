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
export const GlobalSearch: React.FC<GlobalSearchProps> = ({ onResultClick, onClose: _onClose }) => {
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

  const liveMessage = loading
    ? 'Searching...'
    : showResults && results.length === 0 && query
      ? `No results found for ${query}`
      : showResults && results.length > 0
        ? `${results.length} result${results.length === 1 ? '' : 's'} found`
        : '';

  return (
    <SearchContainer>
      {/* ARIA live region — announces search state to screen readers (fixes #2547) */}
      <span
        role="status"
        aria-live="polite"
        aria-atomic="true"
        style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap' }}
      >
        {liveMessage}
      </span>
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
