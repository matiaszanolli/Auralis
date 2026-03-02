/**
 * LibraryEmptyState - Empty State Router for Library Views
 *
 * Routes to the appropriate empty state component based on current view and search context:
 * - Favorites view: Shows "No favorites yet" message
 * - Search with query: Shows "No results" message
 * - Library (default): Shows empty library with scan folder action
 */

import React from 'react';
import { EmptyState, EmptyLibrary, NoSearchResults } from '../shared/ui/feedback';

interface LibraryEmptyStateProps {
  view: string;
  searchQuery: string;
  scanning: boolean;
  onScanFolder: () => void;
}

export const LibraryEmptyState: React.FC<LibraryEmptyStateProps> = ({
  view,
  searchQuery,
  scanning,
  onScanFolder,
}) => {
  if (view === 'favourites') {
    return (
      <EmptyState
        icon="music"
        title="No favorites yet"
        description="Click the heart icon on tracks you love to add them here"
      />
    );
  }

  if (searchQuery && searchQuery.trim()) {
    return <NoSearchResults query={searchQuery} />;
  }

  return (
    <EmptyLibrary
      onScanFolder={onScanFolder}
      scanning={scanning}
    />
  );
};

export default LibraryEmptyState;
