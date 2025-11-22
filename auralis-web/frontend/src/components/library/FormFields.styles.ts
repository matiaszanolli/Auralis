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

/**
 * StyledTextField - Base styled TextField for dark theme
 * Used in metadata forms, dialog inputs, and general form fields
 * Features: simple border styling, aurora focus color
 */
export const StyledTextField = styled(TextField)({
  '& .MuiOutlinedInput-root': {
    color: '#fff',
    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
    '&.Mui-focused fieldset': { borderColor: '#667eea' }
  },
  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
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
    background: 'rgba(26, 31, 58, 0.5)',
    backdropFilter: 'blur(8px)',
    border: '1px solid transparent',
    transition: 'all 0.3s ease',
    paddingRight: '8px',

    '& fieldset': {
      border: 'none',
    },

    '&:hover': {
      background: 'rgba(26, 31, 58, 0.7)',
      border: `1px solid ${auroraOpacity.standard}`,
    },

    '&.Mui-focused': {
      background: 'rgba(26, 31, 58, 0.8)',
      border: `1px solid ${auroraOpacity.stronger}`,
      boxShadow: `0 0 0 3px ${auroraOpacity.veryLight}`,
    },
  },

  '& .MuiOutlinedInput-input': {
    fontSize: '16px',
    color: '#fff',
    padding: '12px 16px',

    '&::placeholder': {
      color: 'rgba(255,255,255,0.5)',
      opacity: 1,
    },
  },

  '& .MuiInputAdornment-root': {
    marginRight: '8px',
    color: 'rgba(255,255,255,0.7)',
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
    color: '#fff',
    '& fieldset': { borderColor: 'rgba(255,255,255,0.15)' },
    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.25)' },
    '&.Mui-focused fieldset': { borderColor: '#667eea' }
  },
  '& .MuiOutlinedInput-input': {
    padding: '8px 12px',
  },
  '& .MuiInputLabel-root': {
    color: 'rgba(255,255,255,0.6)',
    fontSize: '0.875rem'
  }
}));

export default StyledTextField;
