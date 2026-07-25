import { MouseEvent } from 'react';
import { ToggleButtonGroup, ToggleButton, styled } from '@mui/material';
import ViewModule from '@mui/icons-material/ViewModule';
import ViewList from '@mui/icons-material/ViewList';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

export type ViewMode = 'grid' | 'list';

interface ViewToggleProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
}

const StyledToggleButtonGroup = styled(ToggleButtonGroup)({
  background: themeVars.surfaceSecondary,
  borderRadius: tokens.borderRadius.sm,                 // 8px
  padding: tokens.spacing.xs,                           // 4px
  gap: tokens.spacing.xs,                               // 4px
  border: `1px solid ${themeVars.borderDefault}`,
});

const StyledToggleButton = styled(ToggleButton)({
  border: 'none',
  borderRadius: tokens.borderRadius.sm,                    // 8px (close to 6px)
  padding: `${tokens.spacing.cluster} ${tokens.spacing.md}`,  // 8px 12px
  color: themeVars.textSecondary,
  transition: tokens.transitions.base,                  // 200ms (close to 300ms)

  '&:hover': {
    background: themeVars.accentSoft,
    color: themeVars.textPrimary,
  },

  '&.Mui-selected': {
    background: themeVars.accentSoft,
    color: themeVars.accent,
    boxShadow: 'none',

    '&:hover': {
      background: themeVars.accentSoft,
    },
  },

  '& .MuiSvgIcon-root': {
    fontSize: tokens.typography.fontSize.xl,            // 24px (close to 20px)
  },
});

export const ViewToggle = ({ value, onChange }: ViewToggleProps) => {
  const handleChange = (_event: MouseEvent<HTMLElement>, newValue: ViewMode | null) => {
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
