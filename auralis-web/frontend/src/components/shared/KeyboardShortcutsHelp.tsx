/**
 * KeyboardShortcutsHelp Component
 *
 * Displays a beautiful dialog showing all available keyboard shortcuts.
 * Automatically groups shortcuts by category and formats them nicely.
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
import {
  DialogContent,
  IconButton,
  Box,
  Typography,
  Paper,
  Divider,
  styled
} from '@mui/material';
import { Close, Keyboard } from '@mui/icons-material';
import { ShortcutDefinition } from '../../services/keyboardShortcutsService';
import { StyledDialog, StyledDialogTitle } from '../library/Dialog.styles';
import { auroraOpacity, colorAuroraPrimary } from '../library/Color.styles';
import { spacingSmall, spacingXSmall } from '../library/Spacing.styles';

interface KeyboardShortcutsHelpProps {
  open: boolean;
  shortcuts: ShortcutDefinition[];
  onClose: () => void;
  formatShortcut?: (shortcut: ShortcutDefinition) => string;
}

const CategorySection = styled(Paper)(({ theme }) => ({
  background: auroraOpacity.ultraLight,
  border: `1px solid rgba(255, 255, 255, 0.08)`,
  borderRadius: '12px',
  padding: spacingSmall,
  marginBottom: spacingSmall,
}));

const ShortcutRow = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: `${spacingXSmall} 0`,
  borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
  '&:last-child': {
    borderBottom: 'none',
  },
}));

const ShortcutKey = styled(Box)(({ theme }) => ({
  background: auroraOpacity.standard,
  border: `1px solid ${auroraOpacity.veryStrong}`,
  borderRadius: '6px',
  padding: `${spacingXSmall} 12px`,
  fontFamily: 'monospace',
  fontSize: '14px',
  fontWeight: 'bold',
  color: colorAuroraPrimary,
  minWidth: '80px',
  textAlign: 'center',
  boxShadow: `0 2px 8px ${auroraOpacity.standard}`,
}));

const ShortcutDescription = styled(Typography)(({ theme }) => ({
  color: 'rgba(255, 255, 255, 0.9)',
  fontSize: '14px',
}));

const CategoryTitle = styled(Typography)(({ theme }) => ({
  color: colorAuroraPrimary,
  fontWeight: 'bold',
  fontSize: '16px',
  marginBottom: spacingXSmall,
  display: 'flex',
  alignItems: 'center',
  gap: spacingXSmall,
}));

const EmptyState = styled(Box)(({ theme }) => ({
  textAlign: 'center',
  padding: `40px ${spacingSmall}`,
  color: 'rgba(255, 255, 255, 0.5)',
}));

const KeyboardShortcutsHelp: React.FC<KeyboardShortcutsHelpProps> = ({
  open,
  shortcuts,
  onClose,
  formatShortcut,
}) => {
  // Group shortcuts by category
  const groupedShortcuts: Record<string, ShortcutDefinition[]> = {};
  shortcuts.forEach((shortcut) => {
    if (!groupedShortcuts[shortcut.category]) {
      groupedShortcuts[shortcut.category] = [];
    }
    groupedShortcuts[shortcut.category].push(shortcut);
  });

  // Category order
  const categoryOrder: Array<ShortcutDefinition['category']> = [
    'Playback',
    'Navigation',
    'Library',
    'Queue',
    'Global',
  ];

  // Category icons
  const categoryIcons: Record<ShortcutDefinition['category'], string> = {
    'Playback': '🎵',
    'Navigation': '🧭',
    'Library': '📚',
    'Queue': '📝',
    'Global': '⚙️',
  };

  // Default formatShortcut if not provided
  const defaultFormatShortcut = (shortcut: ShortcutDefinition): string => {
    const parts: string[] = [];
    const isMac = typeof navigator !== 'undefined' &&
                  navigator.platform.toUpperCase().indexOf('MAC') >= 0;

    if (shortcut.ctrl || shortcut.meta) {
      parts.push(isMac ? '⌘' : 'Ctrl');
    }
    if (shortcut.shift) {
      parts.push(isMac ? '⇧' : 'Shift');
    }
    if (shortcut.alt) {
      parts.push(isMac ? '⌥' : 'Alt');
    }

    const keyMap: Record<string, string> = {
      ' ': 'Space',
      'ArrowUp': '↑',
      'ArrowDown': '↓',
      'ArrowLeft': '←',
      'ArrowRight': '→',
      'Enter': '↵',
      'Escape': 'Esc',
      'Delete': 'Del',
    };

    const keyDisplay = keyMap[shortcut.key] || shortcut.key.toUpperCase();
    parts.push(keyDisplay);

    return parts.join(isMac ? '' : '+');
  };

  const formatFn = formatShortcut || defaultFormatShortcut;

  return (
    <StyledDialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
    >
      <StyledDialogTitle>
        <Keyboard />
        <Typography variant="h6" component="div" sx={{ flex: 1 }}>
          Keyboard Shortcuts
        </Typography>
        <IconButton
          onClick={onClose}
          sx={{
            color: 'white',
            '&:hover': {
              background: 'rgba(255, 255, 255, 0.1)',
            },
          }}
        >
          <Close />
        </IconButton>
      </StyledDialogTitle>

      <DialogContent sx={{ p: 3 }}>
        {shortcuts.length === 0 ? (
          <EmptyState>
            <Keyboard sx={{ fontSize: 64, mb: 2, opacity: 0.3 }} />
            <Typography variant="h6" gutterBottom>
              No keyboard shortcuts configured
            </Typography>
            <Typography variant="body2">
              Enable keyboard shortcuts in settings to see available shortcuts here.
            </Typography>
          </EmptyState>
        ) : (
          <>
            {categoryOrder.map((category) => {
              const categoryShortcuts = groupedShortcuts[category];
              if (!categoryShortcuts || categoryShortcuts.length === 0) return null;

              return (
                <CategorySection key={category} elevation={0}>
                  <CategoryTitle>
                    <span>{categoryIcons[category]}</span>
                    {category}
                  </CategoryTitle>
                  {categoryShortcuts.map((shortcut, index) => (
                    <ShortcutRow key={index}>
                      <ShortcutDescription>
                        {shortcut.description}
                      </ShortcutDescription>
                      <ShortcutKey>
                        {formatFn(shortcut)}
                      </ShortcutKey>
                    </ShortcutRow>
                  ))}
                </CategorySection>
              );
            })}

            <Divider sx={{ my: 3, borderColor: 'rgba(255, 255, 255, 0.1)' }} />

            <Box sx={{ textAlign: 'center', color: 'rgba(255, 255, 255, 0.5)' }}>
              <Typography variant="body2">
                Press <strong>?</strong> anytime to show this dialog
              </Typography>
            </Box>
          </>
        )}
      </DialogContent>
    </StyledDialog>
  );
};

export default KeyboardShortcutsHelp;
