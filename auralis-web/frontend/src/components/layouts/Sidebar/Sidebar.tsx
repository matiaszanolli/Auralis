import React from 'react';
import { Box, Divider, IconButton } from '@mui/material';
import { ChevronLeft, LibraryMusic, Album, Person, Favorite, History, Settings } from '@mui/icons-material';
import { tokens } from '@/design-system/tokens';
import { AuroraLogo } from '../../navigation/AuroraLogo';
import ThemeToggle from '../../shared/ui/ThemeToggle';
import PlaylistList from '../../playlist/PlaylistList';
import CollapsedSidebar from './CollapsedSidebar';
import NavigationSection from './NavigationSection';
import { SidebarContainer, SectionLabel, StyledListItemButton } from './SidebarStyles';
import { useSidebarState } from './useSidebarState';
import { ListItemIcon, ListItemText } from '@mui/material';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: (view: string) => void;
  onOpenSettings?: () => void;
}

/**
 * Sidebar - Main navigation sidebar component
 *
 * Features:
 * - Collapsible sidebar with smooth transitions
 * - Library navigation (Songs, Albums, Artists)
 * - Collections (Favorites, Recently Played)
 * - Dynamic playlist list
 * - Theme toggle and settings
 * - Active item highlighting with aurora glow
 */
const SidebarComponent: React.FC<SidebarProps> = ({
  collapsed = false,
  onToggleCollapse,
  onNavigate,
  onOpenSettings,
}) => {
  const { selectedItem, playlistsOpen, handleItemClick, setPlaylistsOpen } = useSidebarState(onNavigate);

  // Navigation items definitions
  const libraryItems = [
    { id: 'songs', label: 'Songs', icon: <LibraryMusic /> },
    { id: 'albums', label: 'Albums', icon: <Album /> },
    { id: 'artists', label: 'Artists', icon: <Person /> },
  ];

  const collectionItems = [
    { id: 'favourites', label: 'Favourites', icon: <Favorite /> },
    { id: 'recent', label: 'Recently Played', icon: <History /> },
  ];

  // Show collapsed variant
  if (collapsed) {
    return <CollapsedSidebar onToggleCollapse={onToggleCollapse} />;
  }

  return (
    <SidebarContainer>
      {/* Header with Aurora Logo */}
      <Box
        sx={{
          p: tokens.spacing.md,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <AuroraLogo size="medium" showText animated />
        <IconButton
          onClick={onToggleCollapse}
          size="small"
          sx={{
            color: tokens.colors.text.secondary,
            transition: tokens.transitions.all,
            '&:hover': {
              color: tokens.colors.text.primary,
              transform: 'scale(1.1)',
            },
          }}
        >
          <ChevronLeft />
        </IconButton>
      </Box>

      <Divider sx={{ borderColor: tokens.colors.border.light }} />

      {/* Main Content - Library and Collections */}
      <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
        {/* Library Section */}
        <SectionLabel>Library</SectionLabel>
        <NavigationSection
          items={libraryItems}
          selectedItem={selectedItem}
          onItemClick={handleItemClick}
        />

        <Divider sx={{ borderColor: tokens.colors.border.light, my: tokens.spacing.md }} />

        {/* Collections Section */}
        <NavigationSection
          items={collectionItems}
          selectedItem={selectedItem}
          onItemClick={handleItemClick}
        />

        <Divider sx={{ borderColor: tokens.colors.border.light, my: tokens.spacing.md }} />

        {/* Playlists Section */}
        <PlaylistList
          selectedPlaylistId={selectedItem.startsWith('playlist-') ? parseInt(selectedItem.replace('playlist-', '')) : undefined}
          onPlaylistSelect={(playlistId) => handleItemClick(`playlist-${playlistId}`)}
        />
      </Box>

      {/* Footer - Settings and Theme Toggle */}
      <Box sx={{ mt: 'auto', p: tokens.spacing.md, borderTop: `1px solid ${tokens.colors.border.light}` }}>
        {/* Settings Button */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm, mb: tokens.spacing.sm }}>
          <Box sx={{ flex: 1 }}>
            <StyledListItemButton onClick={onOpenSettings} isactive="false">
              <ListItemIcon
                sx={{
                  color: tokens.colors.text.secondary,
                  minWidth: `calc(${tokens.spacing.lg} + ${tokens.spacing.sm})`, // 36px
                  transition: tokens.transitions.color,
                }}
              >
                <Settings />
              </ListItemIcon>
              <ListItemText
                primary="Settings"
                primaryTypographyProps={{
                  fontSize: tokens.typography.fontSize.base,
                  fontWeight: tokens.typography.fontWeight.normal,
                  color: tokens.colors.text.secondary,
                }}
              />
            </StyledListItemButton>
          </Box>
        </Box>

        {/* Theme Toggle */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: tokens.spacing.md }}>
          <ThemeToggle size="medium" />
        </Box>
      </Box>
    </SidebarContainer>
  );
};

// Memoize for performance
const Sidebar = React.memo(SidebarComponent);

export default Sidebar;
