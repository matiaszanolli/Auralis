/**
 * Form Field Styles - Reusable TextField styling for forms
 *
 * Consolidates TextField styling patterns across metadata forms, search bars,
 * and other input components. Provides consistent dark-themed input field styling
 * with multiple variants for different contexts.
 *
 * Variants:
 * - StyledTextField: Base form input (metadata, dialogs)
 * - SearchTextField: Search field with rounded pill shape
 * - CompactTextField: Minimal form input for space-constrained layouts
 */

import { TextField, styled } from '@mui/material';
import { auroraOpacity } from './Color.styles';
import { tokens } from '@/design-system/tokens';

/**
 * StyledTextField - Base styled TextField for dark theme
 * Used in metadata forms, dialog inputs, and general form fields
 * Features: simple border styling, aurora focus color
 */
export const StyledTextField = styled(TextField)({
  '& .MuiOutlinedInput-root': {
    color: tokens.colors.text.primary,
    '& fieldset': { borderColor: auroraOpacity.light },
    '&:hover fieldset': { borderColor: auroraOpacity.standard },
    '&.Mui-focused fieldset': { borderColor: tokens.colors.accent.primary }
  },
  '& .MuiInputLabel-root': { color: auroraOpacity.standard }
});

/**
 * SearchTextField - Search field with rounded pill shape
 * Used in search bars and search interfaces
 * Features: rounded borders, blur background, aurora focus glow
 */
export const SearchTextField = styled(TextField)(({ theme }) => ({
  '& .MuiOutlinedInput-root': {
    height: '48px',
    borderRadius: '24px',
    background: auroraOpacity.ultraLight,
    backdropFilter: 'blur(8px)',
    border: '1px solid transparent',
    transition: 'all 0.3s ease',
    paddingRight: '8px',

    '& fieldset': {
      border: 'none',
    },

    '&:hover': {
      background: auroraOpacity.lighter,
      border: `1px solid ${auroraOpacity.standard}`,
    },

    '&.Mui-focused': {
      background: auroraOpacity.light,
      border: `1px solid ${auroraOpacity.stronger}`,
      boxShadow: `0 0 0 3px ${auroraOpacity.veryLight}`,
    },
  },

  '& .MuiOutlinedInput-input': {
    fontSize: '16px',
    color: tokens.colors.text.primary,
    padding: '12px 16px',

    '&::placeholder': {
      color: auroraOpacity.standard,
      opacity: 1,
    },
  },

  '& .MuiInputAdornment-root': {
    marginRight: '8px',
    color: auroraOpacity.standard,
  },
}));

/**
 * CompactTextField - Minimal form input for space-constrained layouts
 * Used in compact forms, inline editing, or mobile layouts
 * Features: reduced padding, minimal borders, dense styling
 */
export const CompactTextField = styled(TextField)(({ theme }) => ({
  '& .MuiOutlinedInput-root': {
    fontSize: '0.875rem',
    color: tokens.colors.text.primary,
    '& fieldset': { borderColor: auroraOpacity.ultraLight },
    '&:hover fieldset': { borderColor: auroraOpacity.lighter },
    '&.Mui-focused fieldset': { borderColor: tokens.colors.accent.primary }
  },
  '& .MuiOutlinedInput-input': {
    padding: '8px 12px',
  },
  '& .MuiInputLabel-root': {
    color: auroraOpacity.lighter,
    fontSize: '0.875rem'
  }
}));

export default StyledTextField;
