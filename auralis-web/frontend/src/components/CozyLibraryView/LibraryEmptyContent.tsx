/**
 * LibraryEmptyContent - what the track list shows when there is nothing to list.
 *
 * Split out of library/CozyLibraryView.tsx (#5840): favourites, no search
 * match, or an empty library each get their own empty state. A failed load is
 * none of those: it gets an error with a Retry, before any of them (#6011).
 */

import { memo } from 'react';
import { EmptyState, EmptyLibrary, NoSearchResults } from '@/components/shared/ui/feedback';

interface LibraryEmptyContentProps {
  view: string;
  searchQuery: string;
  scanning: boolean;
  /** Called with the picked folder when the DropZone was clicked, with nothing for the button. */
  onScanFolder: (selectedFolder?: string) => void;
  /** The load error, when the list is empty because the fetch failed. */
  error?: string | null;
  onRetry?: () => void;
}

export const LibraryEmptyContent = memo<LibraryEmptyContentProps>(
  ({ view, searchQuery, scanning, onScanFolder, error, onRetry }) => {
    // Without this a failed first page rendered "Your library is empty - scan a
    // folder" (or "No favorites yet"): wrong, and no way out but a reload.
    if (error) {
      return (
        <EmptyState
          icon="music"
          title={view === 'favourites' ? "Couldn't load your favorites" : "Couldn't load your library"}
          description={error}
          actionLabel={onRetry ? 'Try again' : undefined}
          onAction={onRetry}
          role="alert"
        />
      );
    }
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
    // A drop yields a drop-root-relative path ("/FolderName"), not a usable absolute
    // one, so it falls back to the picker; a click already picked a real folder and
    // must not open a second picker (#6012).
    return <EmptyLibrary onScanFolder={onScanFolder} onFolderDrop={() => onScanFolder()} scanning={scanning} />;
  }
);

LibraryEmptyContent.displayName = 'LibraryEmptyContent';
