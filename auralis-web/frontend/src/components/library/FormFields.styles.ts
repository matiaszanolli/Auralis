/**
 * Form Field Styles - Reusable TextField styling for metadata forms
 *
 * Consolidates TextField styling patterns used in EditMetadataDialog and other form components.
 * Provides consistent dark-themed input field styling with focus states.
 */

import { TextField, styled } from '@mui/material';

/**
 * StyledTextField - Base styled TextField for dark theme
 * Includes focus state with aurora primary color
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

export default StyledTextField;
