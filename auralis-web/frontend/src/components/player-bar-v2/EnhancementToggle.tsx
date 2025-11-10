/**
 * EnhancementToggle - Toggle audio enhancement on/off
 *
 * Features:
 * - Visual on/off state with color change
 * - Smooth animations
 * - Aurora glow when enabled
 * - Design token styling
 */

import React from 'react';
import { Box, IconButton, Tooltip, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';

interface EnhancementToggleProps {
  isEnabled: boolean;
  onToggle: () => void;
}

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

export const EnhancementToggle: React.FC<EnhancementToggleProps> = React.memo(({
  isEnabled,
  onToggle,
}) => {
  return (
    <Tooltip
      title={isEnabled ? 'Disable audio enhancement' : 'Enable audio enhancement'}
      arrow
      placement="top"
    >
      <EnhancementContainer>
        <ToggleButton
          onClick={onToggle}
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

EnhancementToggle.displayName = 'EnhancementToggle';
