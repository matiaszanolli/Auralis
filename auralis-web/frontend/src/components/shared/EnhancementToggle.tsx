/**
 * EnhancementToggle - Parametrized Enhancement Toggle Component
 *
 * Unified component that supports multiple UI variants for toggling audio enhancement.
 * Consolidates button-style and switch-style toggle patterns.
 *
 * Features:
 * - Multiple variants: "button" (compact icon), "switch" (form control)
 * - Design token styling with aurora glow
 * - Processing state support
 * - Smooth animations and transitions
 * - Accessible with proper ARIA labels and tooltips
 */

import React from 'react';
import {
  Box,
  IconButton,
  Tooltip,
  styled,
  Paper,
  Typography,
  Switch,
  FormControlLabel,
} from '@mui/material';
import { tokens } from '@/design-system/tokens';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';

export type EnhancementToggleVariant = 'button' | 'switch';

export interface EnhancementToggleProps {
  /**
   * Whether enhancement is enabled
   */
  isEnabled: boolean;

  /**
   * Callback when toggle state changes
   */
  onToggle: (enabled: boolean) => void;

  /**
   * UI variant to display
   * @default 'button'
   */
  variant?: EnhancementToggleVariant;

  /**
   * Optional: Show processing/loading state
   */
  isProcessing?: boolean;

  /**
   * Optional: Custom label text (switch variant only)
   */
  label?: string;

  /**
   * Optional: Custom description text (switch variant only)
   */
  description?: string;

  /**
   * Optional: Show description based on enabled state
   */
  showDescription?: boolean;

  /**
   * Optional: Custom tooltip text
   */
  tooltipText?: string;
}

// ============================================================================
// Button Variant Styles
// ============================================================================

const ToggleButton = styled(IconButton)<{ $isEnabled: boolean }>(({ $isEnabled }) => ({
  width: '40px',
  height: '40px',
  color: $isEnabled ? tokens.colors.accent.primary : tokens.colors.text.tertiary,
  background: $isEnabled ? `${tokens.colors.accent.primary}15` : 'transparent',
  border: `2px solid ${$isEnabled ? tokens.colors.accent.primary : tokens.colors.border.medium}`,
  boxShadow: $isEnabled ? tokens.shadows.glow : 'none',
  transition: tokens.transitions.all,

  '&:hover': {
    transform: 'scale(1.1)',
    background: $isEnabled
      ? `${tokens.colors.accent.primary}25`
      : tokens.colors.bg.elevated,
    boxShadow: $isEnabled ? tokens.shadows.glowStrong : tokens.shadows.md,
  },

  '&:active': {
    transform: 'scale(0.95)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
    transition: tokens.transitions.transform,
    transform: $isEnabled ? 'rotate(0deg)' : 'rotate(-180deg)',
  },
}));

const EnhancementLabel = styled(Box)<{ $isEnabled: boolean }>(({ $isEnabled }) => ({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.medium,
  color: $isEnabled ? tokens.colors.accent.primary : tokens.colors.text.tertiary,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  transition: tokens.transitions.color,
  marginTop: tokens.spacing.xs,
  textAlign: 'center',
}));

const EnhancementContainer = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '2px',
});

// ============================================================================
// Switch Variant Styles
// ============================================================================

const SwitchPaper = styled(Paper)<{ $isEnabled: boolean; $isProcessing: boolean }>(
  ({ $isEnabled, $isProcessing }) => ({
    p: tokens.spacing.md,
    mb: tokens.spacing.lg,
    borderRadius: tokens.borderRadius.md,
    background: $isEnabled
      ? `${tokens.colors.accent.primary}1A` // ~10% opacity
      : tokens.colors.bg.tertiary,
    border: `1px solid ${
      $isEnabled
        ? `${tokens.colors.accent.primary}4D` // ~30% opacity
        : tokens.colors.border.light
    }`,
    transition: tokens.transitions.all,
    opacity: $isProcessing ? 0.7 : 1,
  })
);

// ============================================================================
// Button Variant Component
// ============================================================================

const ButtonVariant: React.FC<EnhancementToggleProps> = React.memo(({
  isEnabled,
  onToggle,
  tooltipText,
}) => {
  const defaultTooltip = isEnabled
    ? 'Disable audio enhancement'
    : 'Enable audio enhancement';

  return (
    <Tooltip
      title={tooltipText || defaultTooltip}
      arrow
      placement="top"
    >
      <EnhancementContainer>
        <ToggleButton
          onClick={() => onToggle(!isEnabled)}
          $isEnabled={isEnabled}
          aria-label={isEnabled ? 'Disable enhancement' : 'Enable enhancement'}
        >
          <AutoAwesomeIcon />
        </ToggleButton>
        <EnhancementLabel $isEnabled={isEnabled}>
          {isEnabled ? 'Enhanced' : 'Original'}
        </EnhancementLabel>
      </EnhancementContainer>
    </Tooltip>
  );
});

ButtonVariant.displayName = 'EnhancementToggle.ButtonVariant';

// ============================================================================
// Switch Variant Component
// ============================================================================

const SwitchVariant: React.FC<EnhancementToggleProps> = React.memo(({
  isEnabled,
  onToggle,
  isProcessing = false,
  label = 'Enable Auto-Mastering',
  showDescription = true,
  description,
}) => {
  const defaultDescription = isEnabled
    ? 'Analyzing audio and applying intelligent processing'
    : 'Turn on to enhance your music automatically';

  return (
    <SwitchPaper
      elevation={0}
      $isEnabled={isEnabled}
      $isProcessing={isProcessing}
    >
      <FormControlLabel
        control={
          <Switch
            checked={isEnabled}
            onChange={(e) => onToggle(e.target.checked)}
            disabled={isProcessing}
            sx={{
              '& .MuiSwitch-switchBase.Mui-checked': {
                color: tokens.colors.accent.primary,
              },
              '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                backgroundColor: tokens.colors.accent.primary,
              },
            }}
          />
        }
        label={
          <Typography
            variant="body2"
            sx={{
              fontFamily: tokens.typography.fontFamily.primary,
              fontWeight: tokens.typography.fontWeight.semibold,
              color: tokens.colors.text.primary,
              fontSize: tokens.typography.fontSize.sm,
            }}
          >
            {label}
          </Typography>
        }
      />
      {showDescription && (
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            mt: tokens.spacing.xs,
            ml: `calc(${tokens.spacing.xxl} + ${tokens.spacing.xs})`, // Switch width + gap
            color: tokens.colors.text.secondary,
            fontSize: tokens.typography.fontSize.xs,
            fontFamily: tokens.typography.fontFamily.primary,
          }}
        >
          {description || defaultDescription}
        </Typography>
      )}
    </SwitchPaper>
  );
});

SwitchVariant.displayName = 'EnhancementToggle.SwitchVariant';

// ============================================================================
// Main Component
// ============================================================================

/**
 * EnhancementToggle - Unified enhancement toggle supporting multiple UI variants
 *
 * @example
 * // Button variant (compact, for player bar)
 * <EnhancementToggle
 *   variant="button"
 *   isEnabled={isEnhanced}
 *   onToggle={() => setIsEnhanced(!isEnhanced)}
 * />
 *
 * @example
 * // Switch variant (form control, for enhancement pane)
 * <EnhancementToggle
 *   variant="switch"
 *   isEnabled={isEnhanced}
 *   onToggle={setIsEnhanced}
 *   isProcessing={isProcessing}
 *   label="Enable Auto-Mastering"
 * />
 */
export const EnhancementToggle: React.FC<EnhancementToggleProps> = React.memo(({
  variant = 'button',
  ...props
}) => {
  if (variant === 'switch') {
    return <SwitchVariant {...props} />;
  }

  return <ButtonVariant {...props} />;
});

EnhancementToggle.displayName = 'EnhancementToggle';

export default EnhancementToggle;
