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
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Box,
  Typography,
  Paper,
  Divider,
  styled
} from '@mui/material';
import { Close, Keyboard } from '@mui/icons-material';
import { KeyboardShortcut, formatShortcut } from '../../hooks/useKeyboardShortcuts';

interface KeyboardShortcutsHelpProps {
  open: boolean;
  shortcuts: KeyboardShortcut[];
  onClose: () => void;
}

const StyledDialog = styled(Dialog)(({ theme }) => ({
  '& .MuiDialog-paper': {
    background: 'linear-gradient(135deg, #1a1f3a 0%, #0A0E27 100%)',
    border: '1px solid rgba(102, 126, 234, 0.2)',
    borderRadius: '16px',
    maxWidth: '800px',
    width: '100%',
  },
}));

const StyledDialogTitle = styled(DialogTitle)(({ theme }) => ({
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  color: '#ffffff',
  padding: '24px',
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
}));

const CategorySection = styled(Paper)(({ theme }) => ({
  background: 'rgba(255, 255, 255, 0.03)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: '12px',
  padding: '16px',
  marginBottom: '16px',
}));

const ShortcutRow = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '12px 0',
  borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
  '&:last-child': {
    borderBottom: 'none',
  },
}));

const ShortcutKey = styled(Box)(({ theme }) => ({
  background: 'rgba(102, 126, 234, 0.2)',
  border: '1px solid rgba(102, 126, 234, 0.4)',
  borderRadius: '6px',
  padding: '4px 12px',
  fontFamily: 'monospace',
  fontSize: '14px',
  fontWeight: 'bold',
  color: '#667eea',
  minWidth: '80px',
  textAlign: 'center',
  boxShadow: '0 2px 8px rgba(102, 126, 234, 0.2)',
}));

const ShortcutDescription = styled(Typography)(({ theme }) => ({
  color: 'rgba(255, 255, 255, 0.9)',
  fontSize: '14px',
}));

const CategoryTitle = styled(Typography)(({ theme }) => ({
  color: '#667eea',
  fontWeight: 'bold',
  fontSize: '16px',
  marginBottom: '12px',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
}));

const EmptyState = styled(Box)(({ theme }) => ({
  textAlign: 'center',
  padding: '40px 20px',
  color: 'rgba(255, 255, 255, 0.5)',
}));

const KeyboardShortcutsHelp: React.FC<KeyboardShortcutsHelpProps> = ({
  open,
  shortcuts,
  onClose,
}) => {
  // Group shortcuts by category
  const groupedShortcuts: Record<string, KeyboardShortcut[]> = {};
  shortcuts.forEach((shortcut) => {
    if (!groupedShortcuts[shortcut.category]) {
      groupedShortcuts[shortcut.category] = [];
    }
    groupedShortcuts[shortcut.category].push(shortcut);
  });

  // Category order
  const categoryOrder: Array<KeyboardShortcut['category']> = [
    'Playback',
    'Navigation',
    'Library',
    'Queue',
    'Global',
  ];

  // Category icons
  const categoryIcons: Record<KeyboardShortcut['category'], string> = {
    'Playback': '🎵',
    'Navigation': '🧭',
    'Library': '📚',
    'Queue': '📝',
    'Global': '⚙️',
  };

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
                        {formatShortcut(shortcut)}
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
