import { Menu, MenuItem, styled } from '@mui/material';
import { cardShadows } from '../../library/Styles/Shadow.styles';
import { radiusMedium, radiusSmall } from '../../library/Styles/BorderRadius.styles';
import { spacingXSmall, spacingXMedium } from '../../library/Styles/Spacing.styles';
import { auroraOpacity } from '../../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

/**
 * StyledMenu - Context menu background with backdrop blur
 */
export const StyledMenu = styled(Menu)({
  '& .MuiPaper-root': {
    background: tokens.colors.bg.secondary,
    border: `1px solid ${auroraOpacity.standard}`,
    boxShadow: cardShadows.dropdownDark,
    borderRadius: radiusMedium,
    minWidth: '220px',
    padding: spacingXSmall,
    backdropFilter: 'blur(12px)',
  },
});

/**
 * StyledMenuItem - Menu item with optional destructive styling
 *
 * Supports destructive variant (red) for delete/destructive actions
 */
export const StyledMenuItem = styled(MenuItem)<{ destructive?: boolean }>(
  ({ destructive }) => ({
    borderRadius: radiusSmall,
    padding: `${spacingXMedium} ${spacingXMedium}`,
    margin: `${spacingXSmall} 0`,
    fontSize: '14px',
    color: destructive ? tokens.colors.accent.error : tokens.colors.text.primary,
    transition: 'all 0.2s ease',

    '&:hover': {
      background: destructive ? auroraOpacity.ultraLight : auroraOpacity.lighter,
    },

    '&.Mui-disabled': {
      color: tokens.colors.text.disabled,
      opacity: 0.5,
    },

    '& .MuiListItemIcon-root': {
      color: destructive ? tokens.colors.accent.error : tokens.colors.text.secondary,
      minWidth: 36,
    },
  })
);
