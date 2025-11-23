import { useEffect } from 'react';

interface UseLibraryKeyboardShortcutsProps {
  filteredTracksCount: number;
  hasSelection: boolean;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onSelectAllInfo: (message: string) => void;
  onClearSelectionInfo: (message: string) => void;
}

/**
 * useLibraryKeyboardShortcuts - Keyboard shortcut handling for library view
 *
 * Manages:
 * - Ctrl+A: Select all tracks (skips when input is focused)
 * - Escape: Clear selection
 *
 * Listens for keydown events and triggers appropriate handlers
 * Cleans up event listeners on unmount
 */
export const useLibraryKeyboardShortcuts = ({
  filteredTracksCount,
  hasSelection,
  onSelectAll,
  onClearSelection,
  onSelectAllInfo,
  onClearSelectionInfo
}: UseLibraryKeyboardShortcutsProps) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      const isInput = target.tagName.toLowerCase() === 'input' ||
                     target.tagName.toLowerCase() === 'textarea' ||
                     target.contentEditable === 'true';

      if (isInput) return;

      // Ctrl/Cmd + A: Select all tracks
      if ((event.ctrlKey || event.metaKey) && event.key === 'a' && filteredTracksCount > 0) {
        event.preventDefault();
        onSelectAll();
        onSelectAllInfo(`Selected all ${filteredTracksCount} tracks`);
      }

      // Escape: Clear selection
      if (event.key === 'Escape' && hasSelection) {
        event.preventDefault();
        onClearSelection();
        onClearSelectionInfo('Selection cleared');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [filteredTracksCount, hasSelection, onSelectAll, onClearSelection, onSelectAllInfo, onClearSelectionInfo]);
};

export default useLibraryKeyboardShortcuts;
