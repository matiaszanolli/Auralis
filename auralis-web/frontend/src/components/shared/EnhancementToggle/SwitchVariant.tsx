import React from 'react';
import { Switch, FormControlLabel, Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { SwitchPaper } from './EnhancementToggleStyles';
import { EnhancementToggleProps } from './EnhancementToggle';

/**
 * Switch variant of EnhancementToggle
 * Form control style with description text, suitable for enhancement panes
 *
 * Features:
 * - Form-oriented design
 * - Optional description text
 * - Processing state feedback
 * - Larger interactive area
 */
export const SwitchVariant: React.FC<EnhancementToggleProps> = React.memo(({
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

export default SwitchVariant;
