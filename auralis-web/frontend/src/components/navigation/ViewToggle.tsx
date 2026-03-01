import React from 'react';
import { ToggleButtonGroup, ToggleButton, styled } from '@mui/material';
import { ViewModule, ViewList } from '@mui/icons-material';
import { tokens } from '@/design-system';

export type ViewMode = 'grid' | 'list';

interface ViewToggleProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
}

const StyledToggleButtonGroup = styled(ToggleButtonGroup)({
  background: tokens.colors.bg.tertiary,
  borderRadius: tokens.borderRadius.sm,                 // 8px
  padding: tokens.spacing.xs,                           // 4px
  gap: tokens.spacing.xs,                               // 4px
  border: `1px solid ${tokens.colors.opacityScale.accent.standard}`,
});

const StyledToggleButton = styled(ToggleButton)({
  border: 'none',
  borderRadius: tokens.borderRadius.sm,                    // 8px (close to 6px)
  padding: `${tokens.spacing.cluster} ${tokens.spacing.md}`,  // 8px 12px
  color: tokens.colors.text.secondary,
  transition: tokens.transitions.base,                  // 200ms (close to 300ms)

  '&:hover': {
    background: tokens.colors.opacityScale.accent.veryLight,
    color: tokens.colors.text.primary,
  },

  '&.Mui-selected': {
    background: tokens.gradients.aurora,
    color: tokens.colors.text.primary,                  // White text
    boxShadow: `0 2px 8px ${tokens.colors.opacityScale.accent.strong}`,    // Button depth

    '&:hover': {
      background: tokens.gradients.aurora,
      filter: 'brightness(1.1)',                        // Slight brighten on hover
    },
  },

  '& .MuiSvgIcon-root': {
    fontSize: tokens.typography.fontSize.xl,            // 24px (close to 20px)
  },
});

export const ViewToggle: React.FC<ViewToggleProps> = ({ value, onChange }) => {
  const handleChange = (_event: React.MouseEvent<HTMLElement>, newValue: ViewMode | null) => {
    if (newValue !== null) {
      onChange(newValue);
    }
  };

  return (
    <StyledToggleButtonGroup
      value={value}
      exclusive
      onChange={handleChange}
      aria-label="view mode"
    >
      <StyledToggleButton value="grid" aria-label="grid view">
        <ViewModule />
      </StyledToggleButton>
      <StyledToggleButton value="list" aria-label="list view">
        <ViewList />
      </StyledToggleButton>
    </StyledToggleButtonGroup>
  );
};

export default ViewToggle;
