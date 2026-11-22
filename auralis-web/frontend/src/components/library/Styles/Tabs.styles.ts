/**
 * Tabs Styles - Reusable tab component styling
 *
 * Consolidates tab navigation patterns with aurora indicator styling
 * used by dialogs.
 *
 * Includes:
 * - DialogTabs: Compact tabs for dialog interfaces (minHeight: 48)
 *
 * Uses the accent color for the selected state and indicator.
 */

import { Tabs, styled } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

/**
 * DialogTabs - Tab navigation for dialog interfaces
 * Compact styling (minHeight 48, fontSize 0.95rem) for dialog content
 * Used by: SettingsDialog, CreatePlaylistDialog, EditPlaylistDialog
 */
export const DialogTabs = styled(Tabs)({
  borderBottom: `1px solid ${tokens.colors.border.light}`,
  minHeight: 48,
  '& .MuiTab-root': {
    textTransform: 'none',
    fontSize: tokens.typography.fontSize.base,
    minHeight: 48,
    color: themeVars.textSecondary,
    '&.Mui-selected': {
      color: tokens.colors.accent.primary
    }
  },
  '& .MuiTabs-indicator': {
    backgroundColor: tokens.colors.accent.primary
  }
});
