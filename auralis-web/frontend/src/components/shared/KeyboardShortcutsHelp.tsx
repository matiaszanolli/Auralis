/**
 * KeyboardShortcutsHelp Component
 *
 * Displays a beautiful dialog showing all available keyboard shortcuts.
 * Automatically groups shortcuts by category and formats them nicely.
 *
 * Modular structure:
 * - KeyboardShortcutsHeader - Dialog title with close button
 * - KeyboardShortcutsEmpty - Empty state message
 * - KeyboardShortcutsList - Grouped shortcuts and categories
 * - useShortcutFormatting - Memoized grouping and formatting logic
 *
 * Usage:
 * ```tsx
 * <KeyboardShortcutsHelp
 *   open={isHelpOpen}
 *   shortcuts={shortcuts}
 *   onClose={closeHelp}
 * />
 * ```
 */

import React from 'react';
import { DialogContent } from '@mui/material';
import { ShortcutDefinition } from '../../services/keyboardShortcutsService';
import { StyledDialog } from '../library/Dialog.styles';
import { useShortcutFormatting } from './useShortcutFormatting';
import { KeyboardShortcutsHeader } from './KeyboardShortcutsHeader';
import { KeyboardShortcutsEmpty } from './KeyboardShortcutsEmpty';
import { KeyboardShortcutsList } from './KeyboardShortcutsList';
import { DialogContentBox } from './KeyboardShortcutsHelp.styles';

interface KeyboardShortcutsHelpProps {
  open: boolean;
  shortcuts: ShortcutDefinition[];
  onClose: () => void;
  formatShortcut?: (shortcut: ShortcutDefinition) => string;
}

const KeyboardShortcutsHelp: React.FC<KeyboardShortcutsHelpProps> = ({
  open,
  shortcuts,
  onClose,
  formatShortcut,
}) => {
  const { groupedShortcuts, config, formatFn } = useShortcutFormatting(
    shortcuts,
    formatShortcut
  );

  // Build categories array for rendering
  const categories = config.categoryOrder
    .map((category) => ({
      category,
      shortcuts: groupedShortcuts[category] || [],
      icon: config.categoryIcons[category],
    }))
    .filter((cat) => cat.shortcuts.length > 0);

  return (
    <StyledDialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
    >
      <KeyboardShortcutsHeader onClose={onClose} />

      <DialogContent sx={DialogContentBox}>
        {shortcuts.length === 0 ? (
          <KeyboardShortcutsEmpty />
        ) : (
          <KeyboardShortcutsList
            categories={categories}
            formatShortcut={formatFn}
          />
        )}
      </DialogContent>
    </StyledDialog>
  );
};

export default KeyboardShortcutsHelp;
