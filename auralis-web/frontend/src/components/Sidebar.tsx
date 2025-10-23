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
import { colors, gradients } from '../theme/auralisTheme';
import PlaylistList from './playlist/PlaylistList';
import ThemeToggle from './ThemeToggle';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: (view: string) => void;
  onOpenSettings?: () => void;
}

const SidebarContainer = styled(Box)({
  width: '240px',
  height: '100%',
  background: colors.background.secondary,
  borderRight: `1px solid rgba(102, 126, 234, 0.1)`,
  display: 'flex',
  flexDirection: 'column',
  transition: 'width 0.3s ease',
});

const SectionLabel = styled(Typography)({
  fontSize: '11px',
  fontWeight: 600,
  color: colors.text.disabled,
  textTransform: 'uppercase',
  letterSpacing: '1px',
  padding: '16px 24px 8px',
});

const StyledListItemButton = styled(ListItemButton)<{ isactive?: string }>(({ isactive }) => ({
  borderRadius: '8px',
  height: '40px',
  marginBottom: '4px',
  position: 'relative',
  transition: 'all 0.2s ease',

  ...(isactive === 'true' && {
    background: 'rgba(102, 126, 234, 0.15)',
    '&::before': {
      content: '""',
      position: 'absolute',
      left: 0,
      top: 0,
      bottom: 0,
      width: '3px',
      background: gradients.aurora,
      borderRadius: '0 2px 2px 0',
    },
  }),

  '&:hover': {
    background: isactive === 'true'
      ? 'rgba(102, 126, 234, 0.2)'
      : colors.background.hover,
    transform: 'translateX(2px)',
  },
}));

const Sidebar: React.FC<SidebarProps> = ({ collapsed = false, onToggleCollapse, onNavigate, onOpenSettings }) => {
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
          width: 64,
          height: '100%',
          background: colors.background.secondary,
          borderRight: `1px solid rgba(102, 126, 234, 0.1)`,
          display: 'flex',
          flexDirection: 'column',
          transition: 'width 0.3s ease'
        }}
      >
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'center' }}>
          <IconButton onClick={onToggleCollapse} sx={{ color: colors.text.secondary }}>
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
          p: 2,
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
            color: colors.text.secondary,
            transition: 'all 0.2s ease',
            '&:hover': {
              color: colors.text.primary,
              transform: 'scale(1.1)',
            },
          }}
        >
          <ChevronLeft />
        </IconButton>
      </Box>

      <Divider sx={{ borderColor: 'rgba(102, 126, 234, 0.1)' }} />

      {/* Library Section */}
      <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
        <SectionLabel>Library</SectionLabel>
        <List sx={{ px: 2 }}>
          {libraryItems.map((item) => (
            <ListItem key={item.id} disablePadding>
              <StyledListItemButton
                isactive={selectedItem === item.id ? 'true' : 'false'}
                onClick={() => handleItemClick(item.id)}
              >
                <ListItemIcon
                  sx={{
                    color: selectedItem === item.id ? '#667eea' : colors.text.secondary,
                    minWidth: 36,
                    transition: 'color 0.2s ease',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    fontSize: 14,
                    fontWeight: selectedItem === item.id ? 600 : 400,
                    color: selectedItem === item.id ? colors.text.primary : colors.text.secondary,
                  }}
                />
              </StyledListItemButton>
            </ListItem>
          ))}
        </List>

        <Divider sx={{ borderColor: 'rgba(102, 126, 234, 0.1)', my: 2 }} />

        {/* Collections Section */}
        <List sx={{ px: 2 }}>
          {collectionItems.map((item) => (
            <ListItem key={item.id} disablePadding>
              <StyledListItemButton
                isactive={selectedItem === item.id ? 'true' : 'false'}
                onClick={() => handleItemClick(item.id)}
              >
                <ListItemIcon
                  sx={{
                    color: selectedItem === item.id ? '#667eea' : colors.text.secondary,
                    minWidth: 36,
                    transition: 'color 0.2s ease',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    fontSize: 14,
                    fontWeight: selectedItem === item.id ? 600 : 400,
                    color: selectedItem === item.id ? colors.text.primary : colors.text.secondary,
                  }}
                />
              </StyledListItemButton>
            </ListItem>
          ))}
        </List>

        <Divider sx={{ borderColor: 'rgba(102, 126, 234, 0.1)', my: 2 }} />

        {/* Playlists Section - Using PlaylistList Component */}
        <PlaylistList
          selectedPlaylistId={selectedItem.startsWith('playlist-') ? parseInt(selectedItem.replace('playlist-', '')) : undefined}
          onPlaylistSelect={(playlistId) => handleItemClick(`playlist-${playlistId}`)}
        />
      </Box>

      {/* Settings and Theme Toggle at Bottom */}
      <Box sx={{ mt: 'auto', p: 2, borderTop: '1px solid rgba(102, 126, 234, 0.1)' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Box sx={{ flex: 1 }}>
            <StyledListItemButton
              onClick={onOpenSettings}
              isactive="false"
            >
              <ListItemIcon
                sx={{
                  color: colors.text.secondary,
                  minWidth: 36,
                  transition: 'color 0.2s ease',
                }}
              >
                <Settings />
              </ListItemIcon>
              <ListItemText
                primary="Settings"
                primaryTypographyProps={{
                  fontSize: 14,
                  fontWeight: 400,
                  color: colors.text.secondary,
                }}
              />
            </StyledListItemButton>
          </Box>
        </Box>

        {/* Theme Toggle */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          <ThemeToggle size="medium" />
        </Box>
      </Box>
    </SidebarContainer>
  );
};

export default Sidebar;
