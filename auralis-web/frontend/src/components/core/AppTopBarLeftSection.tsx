import React from 'react';

import MenuIcon from '@mui/icons-material/Menu';
import { LeftSection, TitleBox } from './AppTopBar.styles';
import { IconButton, tokens } from '@/design-system';

interface AppTopBarLeftSectionProps {
  showMobileMenu: boolean;
  title: string;
  onOpenMobileDrawer: () => void;
}

/**
 * AppTopBarLeftSection - Left side with mobile menu button or title
 *
 * Shows hamburger menu on mobile, title on desktop.
 */
export const AppTopBarLeftSection: React.FC<AppTopBarLeftSectionProps> = ({
  showMobileMenu,
  title,
  onOpenMobileDrawer,
}) => {
  return (
    <LeftSection sx={{ flex: showMobileMenu ? 0 : 1 }}>
      {showMobileMenu && (
        <IconButton
          onClick={onOpenMobileDrawer}
          sx={{
            color: 'var(--silver)',
            padding: '8px',
            '&:hover': {
              background: tokens.colors.opacityScale.accent.veryLight,
            },
          }}
        >
          <MenuIcon />
        </IconButton>
      )}

      {!showMobileMenu && <TitleBox>{title}</TitleBox>}
    </LeftSection>
  );
};

export default AppTopBarLeftSection;
