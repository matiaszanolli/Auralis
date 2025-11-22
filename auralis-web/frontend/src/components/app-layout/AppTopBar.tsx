import React, { useState } from 'react';
import {
  Box,
  TextField,
  IconButton,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';
import { auroraOpacity } from '../library/Color.styles';

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

  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchFocused, setIsSearchFocused] = useState(false);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);
    onSearch(query);
  };

  const handleSearchClear = () => {
    setSearchQuery('');
    onSearch('');
    onSearchClear?.();
  };

  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return '#4ade80'; // Green
      case 'connecting':
        return '#facc15'; // Yellow
      case 'disconnected':
        return '#ef4444'; // Red
      default:
        return '#888888';
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 24px',
        background: 'var(--midnight-blue)',
        borderBottom: `1px solid ${auroraOpacity.veryLight}`,
        height: 70,
        gap: 16,
      }}
    >
      {/* Left side: Mobile menu button or title */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flex: shouldShowMobileMenu ? 0 : 1,
        }}
      >
        {shouldShowMobileMenu && (
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

        {!shouldShowMobileMenu && (
          <Box
            sx={{
              fontSize: '20px',
              fontWeight: 600,
              color: 'var(--silver)',
              whiteSpace: 'nowrap',
            }}
          >
            {title}
          </Box>
        )}
      </Box>

      {/* Right side: Search input and status indicator */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flex: 1,
          justifyContent: 'flex-end',
        }}
      >
        {/* Search input */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            background: auroraOpacity.minimal,
            borderRadius: '8px',
            border: `1px solid ${
              isSearchFocused
                ? auroraOpacity.strong
                : auroraOpacity.veryLight
            }`,
            padding: '8px 12px',
            gap: 8,
            minWidth: shouldShowMobileMenu ? 200 : 300,
            transition: 'all 0.2s ease',
          }}
        >
          <SearchIcon
            sx={{
              color: 'rgba(255, 255, 255, 0.5)',
              fontSize: '18px',
            }}
          />
          <TextField
            placeholder="Search tracks, albums, artists..."
            value={searchQuery}
            onChange={handleSearchChange}
            onFocus={() => setIsSearchFocused(true)}
            onBlur={() => setIsSearchFocused(false)}
            sx={{
              flex: 1,
              '& .MuiOutlinedInput-root': {
                border: 'none',
                padding: 0,
              },
              '& .MuiOutlinedInput-input': {
                padding: 0,
                color: 'var(--silver)',
                fontSize: '14px',
                '&::placeholder': {
                  color: 'rgba(255, 255, 255, 0.4)',
                  opacity: 1,
                },
              },
              '& .MuiOutlinedInput-notchedOutline': {
                border: 'none',
              },
            }}
          />
          {searchQuery && (
            <IconButton
              onClick={handleSearchClear}
              size="small"
              sx={{
                color: 'rgba(255, 255, 255, 0.5)',
                padding: '4px',
                '&:hover': {
                  color: 'var(--silver)',
                },
              }}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          )}
        </Box>

        {/* Connection status indicator */}
        <Box
          sx={{
            width: 12,
            height: 12,
            borderRadius: '50%',
            background: getConnectionStatusColor(),
            boxShadow: `0 0 8px ${getConnectionStatusColor()}80`,
            minWidth: 12,
          }}
        />
      </Box>
    </Box>
  );
};

export default AppTopBar;
