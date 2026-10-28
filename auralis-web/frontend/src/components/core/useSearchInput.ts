import { useEffect, useRef, useState, useCallback } from 'react';
import { SEARCH_DEBOUNCE_MS } from '@/config/timing';

export interface UseSearchInputProps {
  onSearch: (query: string) => void;
  onSearchClear?: () => void;
  /**
   * The app's current search query, when the parent owns one. The field follows
   * the parent only when it is RESET to empty (Escape clears the app's query,
   * #6013). Other values are the debounced echo of what was typed here; adopting
   * them would overwrite keystrokes made since.
   */
  externalQuery?: string;
}


/**
 * useSearchInput - Manages search input state and handlers
 *
 * Handles:
 * - Search query state (echoed into the field immediately)
 * - Debounced search callback (onSearch fires once typing settles)
 * - Search input focus state
 * - Search change and clear callbacks
 * - Following a parent-side reset of the query (#6013)
 */
export const useSearchInput = ({ onSearch, onSearchClear, externalQuery }: UseSearchInputProps) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(debounceRef.current), []);

  // The parent cleared the query behind our back: empty the field too, and drop
  // a pending debounce so it cannot put the old text back.
  useEffect(() => {
    if (externalQuery === '') {
      clearTimeout(debounceRef.current);
      setSearchQuery('');
    }
  }, [externalQuery]);

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
