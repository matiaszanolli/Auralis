import React, { useState } from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Typography,
  Collapse,
  IconButton,
  styled
} from '@mui/material';
import {
  LibraryMusic,
  Album,
  Person,
  PlaylistPlay,
  Favorite,
  History,
  ExpandMore,
  Add,
  ChevronLeft,
  ChevronRight,
  Settings
} from '@mui/icons-material';
import { AuroraLogo } from './navigation/AuroraLogo';
import { tokens, withOpacity } from '@/design-system/tokens';
import PlaylistList from './playlist/PlaylistList';
import ThemeToggle from './ThemeToggle';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: (view: string) => void;
  onOpenSettings?: () => void;
}

const SidebarContainer = styled(Box)({
  width: tokens.components.sidebar.width,
  height: '100%',
  background: tokens.colors.bg.secondary,
  borderRight: `1px solid ${tokens.colors.border.light}`,
  display: 'flex',
  flexDirection: 'column',
  transition: `width ${tokens.transitions.slow}`,
});

const SectionLabel = styled(Typography)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.disabled,
  textTransform: 'uppercase',
  letterSpacing: '1px',
  padding: `${tokens.spacing.md} ${tokens.spacing.lg} ${tokens.spacing.sm}`,
});

const StyledListItemButton = styled(ListItemButton)<{ isactive?: string }>(({ isactive }) => ({
  borderRadius: tokens.borderRadius.md,
  height: `calc(${tokens.spacing.lg} + ${tokens.spacing.md})`, // 40px (24 + 16)
  marginBottom: tokens.spacing.xs,
  position: 'relative',
  transition: tokens.transitions.all,

  ...(isactive === 'true' && {
    background: withOpacity(tokens.colors.accent.primary, 0.15),
    '&::before': {
      content: '""',
      position: 'absolute',
      left: 0,
      top: 0,
      bottom: 0,
      width: '3px',
      background: tokens.gradients.aurora,
      borderRadius: '0 2px 2px 0',
    },
  }),

  '&:hover': {
    background: isactive === 'true'
      ? withOpacity(tokens.colors.accent.primary, 0.2)
      : tokens.colors.bg.elevated,
    transform: 'translateX(2px)',
  },
}));

const SidebarComponent: React.FC<SidebarProps> = ({ collapsed = false, onToggleCollapse, onNavigate, onOpenSettings }) => {
  const [playlistsOpen, setPlaylistsOpen] = useState(true);
  const [selectedItem, setSelectedItem] = useState('songs');

  const libraryItems = [
    { id: 'songs', label: 'Songs', icon: <LibraryMusic /> },
    { id: 'albums', label: 'Albums', icon: <Album /> },
    { id: 'artists', label: 'Artists', icon: <Person /> }
  ];

  const collectionItems = [
    { id: 'favourites', label: 'Favourites', icon: <Favorite /> },
    { id: 'recent', label: 'Recently Played', icon: <History /> }
  ];

  // Mock playlists - will be replaced with actual data
  const playlists = [
    { id: 'playlist-1', name: 'Chill Vibes' },
    { id: 'playlist-2', name: 'Workout Mix' },
    { id: 'playlist-3', name: 'Focus Flow' }
  ];

  const handleItemClick = (itemId: string) => {
    setSelectedItem(itemId);
    if (onNavigate) {
      onNavigate(itemId);
    }
  };

  if (collapsed) {
    return (
      <Box
        sx={{
          width: tokens.spacing.xxxl, // 64px
          height: '100%',
          background: tokens.colors.bg.secondary,
          borderRight: `1px solid ${tokens.colors.border.light}`,
          display: 'flex',
          flexDirection: 'column',
          transition: `width ${tokens.transitions.slow}`
        }}
      >
        <Box sx={{ p: tokens.spacing.md, display: 'flex', justifyContent: 'center' }}>
          <IconButton onClick={onToggleCollapse} sx={{ color: tokens.colors.text.secondary }}>
            <ChevronRight />
          </IconButton>
        </Box>
      </Box>
    );
  }

  return (
    <SidebarContainer>
      {/* Header with Aurora Logo */}
      <Box
        sx={{
          p: tokens.spacing.md,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
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

      {/* Library Section */}
      <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
        <SectionLabel>Library</SectionLabel>
        <List sx={{ px: tokens.spacing.md }}>
          {libraryItems.map((item) => (
            <ListItem key={item.id} disablePadding>
              <StyledListItemButton
                isactive={selectedItem === item.id ? 'true' : 'false'}
                onClick={() => handleItemClick(item.id)}
              >
                <ListItemIcon
                  sx={{
                    color: selectedItem === item.id ? tokens.colors.accent.primary : tokens.colors.text.secondary,
                    minWidth: `calc(${tokens.spacing.lg} + ${tokens.spacing.sm})`, // 32px + 4px = 36px
                    transition: tokens.transitions.color,
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    fontSize: tokens.typography.fontSize.base,
                    fontWeight: selectedItem === item.id ? tokens.typography.fontWeight.semibold : tokens.typography.fontWeight.normal,
                    color: selectedItem === item.id ? tokens.colors.text.primary : tokens.colors.text.secondary,
                  }}
                />
              </StyledListItemButton>
            </ListItem>
          ))}
        </List>

        <Divider sx={{ borderColor: tokens.colors.border.light, my: tokens.spacing.md }} />

        {/* Collections Section */}
        <List sx={{ px: tokens.spacing.md }}>
          {collectionItems.map((item) => (
            <ListItem key={item.id} disablePadding>
              <StyledListItemButton
                isactive={selectedItem === item.id ? 'true' : 'false'}
                onClick={() => handleItemClick(item.id)}
              >
                <ListItemIcon
                  sx={{
                    color: selectedItem === item.id ? tokens.colors.accent.primary : tokens.colors.text.secondary,
                    minWidth: `calc(${tokens.spacing.lg} + ${tokens.spacing.sm})`, // 36px
                    transition: tokens.transitions.color,
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    fontSize: tokens.typography.fontSize.base,
                    fontWeight: selectedItem === item.id ? tokens.typography.fontWeight.semibold : tokens.typography.fontWeight.normal,
                    color: selectedItem === item.id ? tokens.colors.text.primary : tokens.colors.text.secondary,
                  }}
                />
              </StyledListItemButton>
            </ListItem>
          ))}
        </List>

        <Divider sx={{ borderColor: tokens.colors.border.light, my: tokens.spacing.md }} />

        {/* Playlists Section - Using PlaylistList Component */}
        <PlaylistList
          selectedPlaylistId={selectedItem.startsWith('playlist-') ? parseInt(selectedItem.replace('playlist-', '')) : undefined}
          onPlaylistSelect={(playlistId) => handleItemClick(`playlist-${playlistId}`)}
        />
      </Box>

      {/* Settings and Theme Toggle at Bottom */}
      <Box sx={{ mt: 'auto', p: tokens.spacing.md, borderTop: `1px solid ${tokens.colors.border.light}` }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm, mb: tokens.spacing.sm }}>
          <Box sx={{ flex: 1 }}>
            <StyledListItemButton
              onClick={onOpenSettings}
              isactive="false"
            >
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
