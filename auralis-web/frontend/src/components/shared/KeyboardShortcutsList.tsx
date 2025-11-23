import React from 'react';
import { Box, Divider, Typography } from '@mui/material';
import { ShortcutDefinition } from '../../services/keyboardShortcutsService';
import {
  CategorySection,
  ShortcutRow,
  ShortcutDescription,
  ShortcutKey,
  CategoryTitle,
} from './KeyboardShortcutsHelp.styles';
import { auroraOpacity } from '../library/Styles/Color.styles';

interface ShortcutCategory {
  category: string;
  shortcuts: ShortcutDefinition[];
  icon: string;
}

interface KeyboardShortcutsListProps {
  categories: ShortcutCategory[];
  formatShortcut: (shortcut: ShortcutDefinition) => string;
}

/**
 * KeyboardShortcutsList - Renders grouped shortcut categories
 *
 * Displays:
 * - Category sections with icons
 * - Individual shortcuts with descriptions and key combinations
 * - Footer hint about showing dialog with ?
 */
export const KeyboardShortcutsList: React.FC<KeyboardShortcutsListProps> = ({
  categories,
  formatShortcut,
}) => {
  return (
    <>
      {categories.map((cat) => (
        <CategorySection key={cat.category} elevation={0}>
          <CategoryTitle>
            <span>{cat.icon}</span>
            {cat.category}
          </CategoryTitle>
          {cat.shortcuts.map((shortcut, index) => (
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
      ))}

      <Divider sx={{ my: 3, borderColor: auroraOpacity.ultraLight }} />

      <Box sx={{ textAlign: 'center', color: auroraOpacity.standard }}>
        <Typography variant="body2">
          Press <strong>?</strong> anytime to show this dialog
        </Typography>
      </Box>
    </>
  );
};

export default KeyboardShortcutsList;
