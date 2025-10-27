/**
 * Keyboard Shortcuts Help Dialog
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Displays all available keyboard shortcuts organized by category.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Box,
  Typography,
  Divider,
  Chip,
  styled
} from '@mui/material';
import { Close, Keyboard } from '@mui/icons-material';
import { KEYBOARD_SHORTCUTS, getShortcutString } from '../../hooks/useKeyboardShortcuts';

interface KeyboardShortcutsDialogProps {
  open: boolean;
  onClose: () => void;
}

const ShortcutKey = styled(Chip)(({ theme }) => ({
  fontFamily: 'monospace',
  fontWeight: 'bold',
  fontSize: '0.85rem',
  padding: '4px 8px',
  height: 'auto',
  backgroundColor: 'rgba(102, 126, 234, 0.15)',
  border: '1px solid rgba(102, 126, 234, 0.3)',
  color: theme.palette.text.primary,
  '& .MuiChip-label': {
    padding: '0 4px'
  }
}));

const ShortcutRow = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: theme.spacing(1, 0),
  '&:not(:last-child)': {
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)'
  }
}));

const CategorySection = styled(Box)(({ theme }) => ({
  marginBottom: theme.spacing(3),
  '&:last-child': {
    marginBottom: 0
  }
}));

export const KeyboardShortcutsDialog: React.FC<KeyboardShortcutsDialogProps> = ({
  open,
  onClose
}) => {
  // Group shortcuts by category
  const categories = KEYBOARD_SHORTCUTS.reduce((acc, shortcut) => {
    if (!acc[shortcut.category]) {
      acc[shortcut.category] = [];
    }
    acc[shortcut.category].push(shortcut);
    return acc;
  }, {} as Record<string, typeof KEYBOARD_SHORTCUTS>);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          background: 'linear-gradient(135deg, #1a1f3a 0%, #0d1028 100%)',
          borderRadius: 2,
          border: '1px solid rgba(102, 126, 234, 0.2)'
        }
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          pb: 2
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Keyboard sx={{ color: '#667eea' }} />
          <Typography variant="h6" fontWeight="bold">
            Keyboard Shortcuts
          </Typography>
        </Box>
        <IconButton
          onClick={onClose}
          size="small"
          sx={{
            color: 'text.secondary',
            '&:hover': {
              backgroundColor: 'rgba(255, 255, 255, 0.1)'
            }
          }}
        >
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ mt: 2 }}>
        {Object.entries(categories).map(([category, shortcuts]) => (
          <CategorySection key={category}>
            <Typography
              variant="overline"
              sx={{
                color: 'text.secondary',
                fontWeight: 'bold',
                fontSize: '0.75rem',
                letterSpacing: 1,
                display: 'block',
                mb: 1
              }}
            >
              {category}
            </Typography>

            <Box>
              {shortcuts.map((shortcut, index) => (
                <ShortcutRow key={index}>
                  <Typography
                    variant="body2"
                    sx={{
                      color: 'text.primary',
                      flex: 1
                    }}
                  >
                    {shortcut.action}
                  </Typography>
                  <ShortcutKey
                    label={getShortcutString(shortcut.key)}
                    size="small"
                  />
                </ShortcutRow>
              ))}
            </Box>
          </CategorySection>
        ))}

        <Divider sx={{ my: 3, borderColor: 'rgba(255, 255, 255, 0.1)' }} />

        <Box
          sx={{
            p: 2,
            backgroundColor: 'rgba(102, 126, 234, 0.1)',
            borderRadius: 1,
            border: '1px solid rgba(102, 126, 234, 0.2)'
          }}
        >
          <Typography variant="caption" color="text.secondary">
            💡 <strong>Tip:</strong> Keyboard shortcuts work from anywhere in the app,
            except when typing in input fields. Press{' '}
            <ShortcutKey label="?" size="small" sx={{ display: 'inline-flex', mx: 0.5 }} />
            {' '}to see this dialog anytime.
          </Typography>
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export default KeyboardShortcutsDialog;
