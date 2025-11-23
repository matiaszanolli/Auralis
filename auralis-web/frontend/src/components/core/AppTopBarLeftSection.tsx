import React from 'react';
import { IconButton } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import { auroraOpacity } from '../library/Color.styles';
import { LeftSection, TitleBox } from './AppTopBar.styles';

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
              background: auroraOpacity.veryLight,
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
