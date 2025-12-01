/**
 * SearchBar Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Search input for querying library (tracks, albums, artists).
 * Debounced input to avoid excessive API calls.
 *
 * Usage:
 * ```typescript
 * <SearchBar onSearch={(query) => setSearch(query)} />
 * ```
 *
 * Props:
 * - onSearch: Callback when search query changes (debounced)
 * - placeholder: Search placeholder text
 *
 * @module components/library/SearchBar
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { tokens } from '@/design-system/tokens';

interface SearchBarProps {
  /** Callback when search query changes (debounced) */
  onSearch: (query: string) => void;

  /** Placeholder text (default: "Search tracks...") */
  placeholder?: string;

  /** Debounce delay in ms (default: 300) */
  debounceMs?: number;

  /** Auto-focus on mount */
  autoFocus?: boolean;
}

/**
 * SearchBar component
 *
 * Text input with debounced search callback.
 * Includes clear button and loading indicator.
 * Optimized for library search queries.
 */
export const SearchBar: React.FC<SearchBarProps> = ({
  onSearch,
  placeholder = 'Search tracks, albums, artists...',
  debounceMs = 300,
  autoFocus = false,
}) => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  /**
   * Handle input change with debouncing
   */
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newQuery = e.target.value;
      setQuery(newQuery);

      // Clear existing timer
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      // Set up new debounced search
      setIsLoading(true);
      debounceTimerRef.current = setTimeout(() => {
        onSearch(newQuery);
        setIsLoading(false);
      }, debounceMs);
    },
    [onSearch, debounceMs]
  );

  /**
   * Handle clear button click
   */
  const handleClear = useCallback(() => {
    setQuery('');
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    onSearch('');
    inputRef.current?.focus();
  }, [onSearch]);

  /**
   * Cleanup timer on unmount
   */
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return (
    <div style={styles.container}>
      <div style={styles.inputWrapper}>
        {/* Search icon */}
        <span style={styles.icon}>🔍</span>

        {/* Search input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          placeholder={placeholder}
          autoFocus={autoFocus}
          style={styles.input}
          aria-label="Search"
        />

        {/* Clear or loading indicator */}
        {query && !isLoading && (
          <button
            onClick={handleClear}
            style={styles.clearButton}
            aria-label="Clear search"
            title="Clear search"
          >
            ✕
          </button>
        )}

        {isLoading && <span style={styles.loadingIcon}>⟳</span>}
      </div>

      {/* Search hint */}
      {!query && (
        <p style={styles.hint}>
          Search by track title, artist name, or album
        </p>
      )}

      {/* Results count */}
      {query && !isLoading && (
        <p style={styles.hint}>
          Searching for "<span style={styles.queryHighlight}>{query}</span>"
        </p>
      )}
    </div>
  );
};

/**
 * Component styles using design tokens
 */
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.sm,
    width: '100%',
  },

  inputWrapper: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.default}`,
    transition: 'border-color 0.2s ease',

    '&:focus-within': {
      borderColor: tokens.colors.accent.primary,
      boxShadow: `0 0 0 2px ${tokens.colors.accent.subtle}`,
    },
  },

  icon: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '16px',
    color: tokens.colors.text.secondary,
    flexShrink: 0,
  },

  input: {
    flex: 1,
    backgroundColor: 'transparent',
    border: 'none',
    outline: 'none',
    fontSize: tokens.typography.fontSize.md,
    color: tokens.colors.text.primary,
    fontFamily: tokens.typography.fontFamily.primary,

    '&::placeholder': {
      color: tokens.colors.text.tertiary,
    },
  },

  clearButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '24px',
    height: '24px',
    padding: 0,
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
    color: tokens.colors.text.secondary,
    fontSize: '16px',
    transition: 'color 0.2s ease',
    flexShrink: 0,

    '&:hover': {
      color: tokens.colors.text.primary,
    },
  },

  loadingIcon: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '16px',
    color: tokens.colors.accent.primary,
    animation: 'spin 1s linear infinite',
    flexShrink: 0,
  },

  hint: {
    margin: 0,
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.tertiary,
    paddingX: tokens.spacing.sm,
  },

  queryHighlight: {
    color: tokens.colors.accent.primary,
    fontWeight: tokens.typography.fontWeight.bold,
  },
};

export default SearchBar;
