/**
 * LibraryEmptyState - Empty State Router for Library Views
 *
 * Displays appropriate empty state based on context:
 * - Favorites view: No favorites yet
 * - Search results: No matches found
 * - Library empty: Prompt to scan folder
 *
 * Extracted from CozyLibraryView.tsx for clarity and reusability.
 */

import React from 'react';
import { EmptyLibrary, NoSearchResults, EmptyState } from '../shared/EmptyState';

export interface LibraryEmptyStateProps {
  view: string;
  searchQuery: string;
  scanning: boolean;
  onScanFolder: () => void;
}

/**
 * Determines which empty state to show based on context
 */
export const LibraryEmptyState: React.FC<LibraryEmptyStateProps> = ({
  view,
  searchQuery,
  scanning,
  onScanFolder
}) => {
  // Favorites view - no favorites yet
  if (view === 'favourites') {
    return (
      <EmptyState
        icon="music"
        title="No favorites yet"
        description="Click the heart icon on tracks you love to add them to your favorites"
      />
    );
  }

  // Search query - no results found
  if (searchQuery) {
    return <NoSearchResults query={searchQuery} />;
  }

  // Library empty - prompt to scan
  return (
    <EmptyLibrary
      onScanFolder={onScanFolder}
      onFolderDrop={onScanFolder}
      scanning={scanning}
    />
  );
};

export default LibraryEmptyState;
