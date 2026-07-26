/**
 * Form Field Styles - Reusable TextField styling for forms
 *
 * Consolidates TextField styling patterns across metadata forms, search bars,
 * and other input components. Provides consistent theme-aware input field styling
 * with multiple variants for different contexts.
 *
 * Variants:
 * - StyledTextField: Base form input (metadata, dialogs)
 * - SearchTextField: Search field with rounded pill shape
 * - CompactTextField: Minimal form input for space-constrained layouts
 */

import { TextField, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

/**
 * StyledTextField - Base styled TextField
 * Used in metadata forms, dialog inputs, and general form fields
 * Features: simple border styling, aurora focus color
 */
export const StyledTextField = styled(TextField)({
  '& .MuiOutlinedInput-root': {
    color: themeVars.textPrimary,
    '& fieldset': { borderColor: themeVars.borderDefault },
    '&:hover fieldset': { borderColor: themeVars.borderStrong },
    '&.Mui-focused fieldset': { borderColor: themeVars.accent },
  },
  '& .MuiInputLabel-root': { color: themeVars.textSecondary },
});

/**
 * SearchTextField - Flat search field with minimal underline
 * Used in search bars and search interfaces
 * Features: transparent background, simple underline, minimal styling
 */
export const SearchTextField = styled(TextField)(({ theme: _theme }) => ({
  '& .MuiOutlinedInput-root': {
    height: tokens.components.searchBar.height,
    borderRadius: 0,
    background: 'transparent',
    border: 'none',
    borderBottom: `1px solid ${themeVars.borderSubtle}`,
    transition: `border-color ${tokens.transitions.hover_out}`,
    paddingRight: tokens.spacing.sm,

    '& fieldset': {
      border: 'none',
    },

    '&:hover': {
      background: 'transparent',
      borderBottom: `1px solid ${themeVars.borderDefault}`,
    },

    '&.Mui-focused': {
      background: 'transparent',
      borderBottom: `1px solid ${themeVars.accent}`,
      boxShadow: 'none',
    },
  },

  '& .MuiOutlinedInput-input': {
    fontSize: tokens.typography.fontSize.md,
    color: themeVars.textPrimary,
    padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,

    '&::placeholder': {
      color: themeVars.textMuted,
      opacity: 0.7,
    },
  },

  '& .MuiInputAdornment-root': {
    marginRight: tokens.spacing.sm,
    color: themeVars.textMuted,
    opacity: 0.6,
  },
}));

/**
 * CompactTextField - Minimal form input for space-constrained layouts
 * Used in compact forms, inline editing, or mobile layouts
 * Features: reduced padding, minimal borders, dense styling
 */
export const CompactTextField = styled(TextField)(({ theme: _theme }) => ({
  '& .MuiOutlinedInput-root': {
    fontSize: tokens.typography.fontSize.sm,
    color: themeVars.textPrimary,
    '& fieldset': { borderColor: themeVars.borderSubtle },
    '&:hover fieldset': { borderColor: themeVars.borderDefault },
    '&.Mui-focused fieldset': { borderColor: themeVars.accent },
  },
  '& .MuiOutlinedInput-input': {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
  },
  '& .MuiInputLabel-root': {
    color: themeVars.textSecondary,
    fontSize: tokens.typography.fontSize.sm,
  },
}));

export default StyledTextField;
