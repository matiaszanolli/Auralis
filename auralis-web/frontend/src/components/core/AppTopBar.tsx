import React from 'react';
import { useMediaQuery, useTheme } from '@mui/material';
import { TopBarContainer, RightSection } from './AppTopBar.styles';
import AppTopBarLeftSection from './AppTopBarLeftSection';
import AppTopBarSearchInput from './AppTopBarSearchInput';
import AppTopBarStatusIndicator from './AppTopBarStatusIndicator';
import { useSearchInput } from './useSearchInput';
import { useConnectionStatus } from './useConnectionStatus';

/**
 * Props for the AppTopBar component.
 */
export interface AppTopBarProps {
  /**
   * Callback when search query changes.
   * Receives the search string.
   */
  onSearch: (query: string) => void;

  /**
   * Callback when mobile drawer toggle button is clicked.
   * Only applicable on mobile screens.
   */
  onOpenMobileDrawer: () => void;

  /**
   * Current page/view title (e.g., 'Library', 'Albums', 'Artists').
   */
  title: string;

  /**
   * Connection status to show in header.
   * 'connected', 'connecting', or 'disconnected'.
   */
  connectionStatus: 'connected' | 'connecting' | 'disconnected';

  /**
   * Whether current screen is mobile (<900px).
   * Determines whether to show hamburger menu.
   */
  isMobile: boolean;

  /**
   * Optional callback when search input is cleared.
   * Called when user clicks clear button or clears the field.
   */
  onSearchClear?: () => void;
}

/**
 * AppTopBar component displays the header with search, title, and mobile controls.
 *
 * Responsibilities:
 * - Display page title
 * - Search input for library search
 * - Mobile hamburger menu button (< 900px)
 * - Connection status indicator
 * - Clear search button
 *
 * Responsive Behavior:
 * - Mobile (<900px): Shows hamburger button on left, title + search on right
 * - Desktop (≥900px): Shows title on left, search on right
 *
 * @param props Component props
 * @returns Rendered top bar with search and title
 *
 * @example
 * ```tsx
 * function AppTopBarExample() {
 *   const [searchQuery, setSearchQuery] = useState('');
 *
 *   return (
 *     <AppTopBar
 *       onSearch={setSearchQuery}
 *       onOpenMobileDrawer={handleDrawerOpen}
 *       title="Library"
 *       connectionStatus="connected"
 *       isMobile={false}
 *     />
 *   );
 * }
 * ```
 */
export const AppTopBar: React.FC<AppTopBarProps> = ({
  onSearch,
  onOpenMobileDrawer,
  title,
  connectionStatus,
  isMobile,
  onSearchClear,
}) => {
  const theme = useTheme();
  const mediaIsMobile = useMediaQuery(theme.breakpoints.down('md'));
  const shouldShowMobileMenu = isMobile || mediaIsMobile;

  // Search input state and handlers
  const {
    searchQuery,
    isSearchFocused,
    setIsSearchFocused,
    handleSearchChange,
    handleSearchClear,
  } = useSearchInput({ onSearch, onSearchClear });

  // Connection status color
  const statusColor = useConnectionStatus(connectionStatus);

  return (
    <TopBarContainer>
      <AppTopBarLeftSection
        showMobileMenu={shouldShowMobileMenu}
        title={title}
        onOpenMobileDrawer={onOpenMobileDrawer}
      />

      <RightSection>
        <AppTopBarSearchInput
          searchQuery={searchQuery}
          isSearchFocused={isSearchFocused}
          minWidth={shouldShowMobileMenu ? 200 : 300}
          onSearchChange={handleSearchChange}
          onFocus={() => setIsSearchFocused(true)}
          onBlur={() => setIsSearchFocused(false)}
          onClear={handleSearchClear}
        />

        <AppTopBarStatusIndicator color={statusColor} />
      </RightSection>
    </TopBarContainer>
  );
};

export default AppTopBar;
