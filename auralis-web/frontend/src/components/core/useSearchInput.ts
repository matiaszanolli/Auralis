import { useEffect, useRef, useState, useCallback } from 'react';
import { SEARCH_DEBOUNCE_MS } from '@/config/timing';

export interface UseSearchInputProps {
  onSearch: (query: string) => void;
  onSearchClear?: () => void;
}


/**
 * useSearchInput - Manages search input state and handlers
 *
 * Handles:
 * - Search query state (echoed into the field immediately)
 * - Debounced search callback (onSearch fires once typing settles)
 * - Search input focus state
 * - Search change and clear callbacks
 */
export const useSearchInput = ({ onSearch, onSearchClear }: UseSearchInputProps) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(debounceRef.current), []);

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const query = e.target.value;
      setSearchQuery(query);
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => onSearch(query), SEARCH_DEBOUNCE_MS);
    },
    [onSearch]
  );

  const handleSearchClear = useCallback(() => {
    clearTimeout(debounceRef.current);
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
