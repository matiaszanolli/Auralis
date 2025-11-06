/**
 * Input Primitive Component
 *
 * Text input field for forms and search.
 *
 * Usage:
 *   <Input placeholder="Search..." />
 *   <Input variant="search" startIcon={<SearchIcon />} />
 *   <Input error errorMessage="Required field" />
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import { styled } from '@mui/material/styles';
import MuiTextField, { TextFieldProps as MuiTextFieldProps } from '@mui/material/TextField';
import { InputAdornment } from '@mui/material';
import { tokens } from '../tokens';

export interface InputProps extends Omit<MuiTextFieldProps, 'variant' | 'size' | 'color'> {
  /**
   * Visual variant
   */
  variant?: 'default' | 'search';

  /**
   * Size
   */
  size?: 'sm' | 'md' | 'lg';

  /**
   * Icon before input
   */
  startIcon?: React.ReactNode;

  /**
   * Icon after input
   */
  endIcon?: React.ReactNode;

  /**
   * Error message to display
   */
  errorMessage?: string;
}

const StyledTextField = styled(MuiTextField, {
  shouldForwardProp: (prop) =>
    !['variant', 'size'].includes(prop as string),
})<InputProps>(({ variant = 'default', size = 'md', error }) => {
  // Size styles
  const sizeStyles = {
    sm: {
      '& .MuiInputBase-root': {
        height: '32px',
        fontSize: tokens.typography.fontSize.sm,
      },
    },
    md: {
      '& .MuiInputBase-root': {
        height: '40px',
        fontSize: tokens.typography.fontSize.base,
      },
    },
    lg: {
      '& .MuiInputBase-root': {
        height: '48px',
        fontSize: tokens.typography.fontSize.md,
      },
    },
  };

  // Variant styles
  const variantStyles = {
    default: {
      '& .MuiInputBase-root': {
        background: tokens.colors.bg.tertiary,
        borderRadius: tokens.borderRadius.md,
        border: `1px solid ${error ? tokens.colors.accent.error : tokens.colors.border.medium}`,
        color: tokens.colors.text.primary,
        transition: tokens.transitions.all,

        '&:hover': {
          borderColor: error ? tokens.colors.accent.error : tokens.colors.border.heavy,
        },

        '&.Mui-focused': {
          borderColor: error ? tokens.colors.accent.error : tokens.colors.accent.primary,
          boxShadow: error
            ? `0 0 0 3px rgba(239, 68, 68, 0.1)`
            : `0 0 0 3px rgba(102, 126, 234, 0.1)`,
        },
      },

      '& .MuiInputBase-input': {
        padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
        color: tokens.colors.text.primary,

        '&::placeholder': {
          color: tokens.colors.text.tertiary,
          opacity: 1,
        },
      },

      '& .MuiOutlinedInput-notchedOutline': {
        border: 'none', // We use custom border
      },
    },

    search: {
      '& .MuiInputBase-root': {
        background: 'rgba(37, 42, 71, 0.6)',
        borderRadius: tokens.borderRadius.full, // Pill shape
        border: `1px solid ${tokens.colors.border.light}`,
        color: tokens.colors.text.primary,
        transition: tokens.transitions.all,
        backdropFilter: 'blur(10px)',

        '&:hover': {
          background: 'rgba(37, 42, 71, 0.8)',
          borderColor: tokens.colors.border.medium,
        },

        '&.Mui-focused': {
          background: 'rgba(37, 42, 71, 0.95)',
          borderColor: tokens.colors.accent.primary,
          boxShadow: tokens.shadows.glow,
        },
      },

      '& .MuiInputBase-input': {
        padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
        color: tokens.colors.text.primary,

        '&::placeholder': {
          color: tokens.colors.text.tertiary,
          opacity: 1,
        },
      },

      '& .MuiOutlinedInput-notchedOutline': {
        border: 'none',
      },
    },
  };

  return {
    ...sizeStyles[size],
    ...variantStyles[variant],

    '& .MuiFormHelperText-root': {
      marginLeft: tokens.spacing.sm,
      marginTop: tokens.spacing.xs,
      fontSize: tokens.typography.fontSize.xs,
      color: error ? tokens.colors.accent.error : tokens.colors.text.tertiary,
    },
  };
});

export const Input: React.FC<InputProps> = ({
  variant = 'default',
  size = 'md',
  startIcon,
  endIcon,
  error = false,
  errorMessage,
  ...props
}) => {
  return (
    <StyledTextField
      variant={variant}
      size={size}
      error={error}
      helperText={errorMessage}
      InputProps={{
        startAdornment: startIcon ? (
          <InputAdornment position="start" sx={{ color: tokens.colors.text.tertiary }}>
            {startIcon}
          </InputAdornment>
        ) : undefined,
        endAdornment: endIcon ? (
          <InputAdornment position="end" sx={{ color: tokens.colors.text.tertiary }}>
            {endIcon}
          </InputAdornment>
        ) : undefined,
      }}
      {...props}
    />
  );
};

export default Input;
