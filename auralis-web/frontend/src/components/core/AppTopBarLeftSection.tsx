
import MenuIcon from '@mui/icons-material/Menu';
import { LeftSection, TitleBox } from './AppTopBar.styles';
import { IconButton } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

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
export const AppTopBarLeftSection = ({
  showMobileMenu,
  title,
  onOpenMobileDrawer,
}: AppTopBarLeftSectionProps) => {
  return (
    <LeftSection sx={{ flex: showMobileMenu ? 0 : 1 }}>
      {showMobileMenu && (
        <IconButton
          onClick={onOpenMobileDrawer}
          aria-label="Open navigation menu"
          sx={{
            color: themeVars.textSecondary,
            padding: '8px',
            '&:hover': {
              background: themeVars.accentSoft,
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
