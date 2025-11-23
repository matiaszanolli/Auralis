import { useState, useCallback } from 'react';

export interface UseSearchInputProps {
  onSearch: (query: string) => void;
  onSearchClear?: () => void;
}

/**
 * useSearchInput - Manages search input state and handlers
 *
 * Handles:
 * - Search query state
 * - Search input focus state
 * - Search change and clear callbacks
 */
export const useSearchInput = ({ onSearch, onSearchClear }: UseSearchInputProps) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchFocused, setIsSearchFocused] = useState(false);

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const query = e.target.value;
      setSearchQuery(query);
      onSearch(query);
    },
    [onSearch]
  );

  const handleSearchClear = useCallback(() => {
    setSearchQuery('');
    onSearch('');
    onSearchClear?.();
  }, [onSearch, onSearchClear]);

  return {
    searchQuery,
    isSearchFocused,
    setIsSearchFocused,
    handleSearchChange,
    handleSearchClear,
  };
};
