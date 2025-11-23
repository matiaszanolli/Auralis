import React from 'react';
import { ToggleButtonGroup, ToggleButton, styled } from '@mui/material';
import { ViewModule, ViewList } from '@mui/icons-material';
import { gradients, auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

export type ViewMode = 'grid' | 'list';

interface ViewToggleProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
}

const StyledToggleButtonGroup = styled(ToggleButtonGroup)({
  background: tokens.colors.bg.tertiary,
  borderRadius: '8px',
  padding: '4px',
  gap: '4px',
  border: `1px solid ${auroraOpacity.standard}`,
});

const StyledToggleButton = styled(ToggleButton)({
  border: 'none',
  borderRadius: '6px !important',
  padding: '8px 12px',
  color: tokens.colors.text.secondary,
  transition: 'all 0.3s ease',

  '&:hover': {
    background: auroraOpacity.veryLight,
    color: tokens.colors.text.primary,
  },

  '&.Mui-selected': {
    background: gradients.aurora,
    color: '#ffffff',
    boxShadow: `0 2px 8px ${auroraOpacity.strong}`,

    '&:hover': {
      background: gradients.aurora,
      filter: 'brightness(1.1)',
    },
  },

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
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
