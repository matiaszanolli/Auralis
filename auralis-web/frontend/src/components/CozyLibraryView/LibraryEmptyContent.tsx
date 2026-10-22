/**
 * LibraryEmptyContent - what the track list shows when there is nothing to list.
 *
 * Split out of library/CozyLibraryView.tsx (#5840): favourites, no search
 * match, or an empty library each get their own empty state.
 */

import { memo } from 'react';
import { EmptyState, EmptyLibrary, NoSearchResults } from '@/components/shared/ui/feedback';

interface LibraryEmptyContentProps {
  view: string;
  searchQuery: string;
  scanning: boolean;
  onScanFolder: () => void;
}

export const LibraryEmptyContent = memo<LibraryEmptyContentProps>(
  ({ view, searchQuery, scanning, onScanFolder }) => {
    if (view === 'favourites') {
      return (
        <EmptyState
          icon="music"
          title="No favorites yet"
          description="Click the heart icon on tracks you love to add them to your favorites"
        />
      );
    }
    if (searchQuery) {
      return <NoSearchResults query={searchQuery} />;
    }
    return <EmptyLibrary onScanFolder={onScanFolder} onFolderDrop={onScanFolder} scanning={scanning} />;
  }
);

LibraryEmptyContent.displayName = 'LibraryEmptyContent';
