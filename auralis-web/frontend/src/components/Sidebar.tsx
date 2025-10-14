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
  IconButton
} from '@mui/material';
import {
  LibraryMusic,
  Album,
  Person,
  PlaylistPlay,
  Favorite,
  History,
  ExpandLess,
  ExpandMore,
  Add,
  ChevronLeft,
  ChevronRight
} from '@mui/icons-material';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ collapsed = false, onToggleCollapse }) => {
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
  };

  if (collapsed) {
    return (
      <Box
        sx={{
          width: 64,
          height: '100%',
          background: 'var(--charcoal)',
          borderRight: '1px solid rgba(226, 232, 240, 0.1)',
          display: 'flex',
          flexDirection: 'column',
          transition: 'width 0.3s ease'
        }}
      >
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'center' }}>
          <IconButton onClick={onToggleCollapse} sx={{ color: 'var(--silver)' }}>
            <ChevronRight />
          </IconButton>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: 240,
        height: '100%',
        background: 'var(--charcoal)',
        borderRight: '1px solid rgba(226, 232, 240, 0.1)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.3s ease'
      }}
    >
      {/* Header with collapse button */}
      <Box
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}
      >
        <Typography
          variant="h6"
          sx={{
            fontFamily: 'var(--font-heading)',
            fontWeight: 600,
            background: 'var(--aurora-gradient)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}
        >
          ✨ Auralis
        </Typography>
        <IconButton onClick={onToggleCollapse} size="small" sx={{ color: 'var(--silver)' }}>
          <ChevronLeft />
        </IconButton>
      </Box>

      <Divider sx={{ borderColor: 'rgba(226, 232, 240, 0.1)' }} />

      {/* Library Section */}
      <Box sx={{ flex: 1, overflowY: 'auto' }}>
        <List sx={{ px: 1, py: 2 }}>
          <Typography
            variant="caption"
            sx={{
              px: 2,
              py: 1,
              display: 'block',
              fontFamily: 'var(--font-body)',
              color: 'var(--silver)',
              opacity: 0.6,
              textTransform: 'uppercase',
              letterSpacing: 1
            }}
          >
            Library
          </Typography>
          {libraryItems.map((item) => (
            <ListItem key={item.id} disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                selected={selectedItem === item.id}
                onClick={() => handleItemClick(item.id)}
                sx={{
                  borderRadius: 'var(--radius-md)',
                  '&.Mui-selected': {
                    background: 'rgba(124, 58, 237, 0.2)',
                    borderLeft: '4px solid',
                    borderImage: 'var(--aurora-gradient) 1',
                    '&:hover': {
                      background: 'rgba(124, 58, 237, 0.3)'
                    }
                  },
                  '&:hover': {
                    background: 'rgba(226, 232, 240, 0.05)'
                  }
                }}
              >
                <ListItemIcon sx={{ color: selectedItem === item.id ? 'var(--aurora-violet)' : 'var(--silver)', minWidth: 40 }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    fontFamily: 'var(--font-body)',
                    fontSize: 14,
                    color: 'var(--silver)'
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>

        <Divider sx={{ borderColor: 'rgba(226, 232, 240, 0.1)', my: 1 }} />

        {/* Collections Section */}
        <List sx={{ px: 1 }}>
          {collectionItems.map((item) => (
            <ListItem key={item.id} disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                selected={selectedItem === item.id}
                onClick={() => handleItemClick(item.id)}
                sx={{
                  borderRadius: 'var(--radius-md)',
                  '&.Mui-selected': {
                    background: 'rgba(124, 58, 237, 0.2)',
                    borderLeft: '4px solid',
                    borderImage: 'var(--aurora-gradient) 1'
                  },
                  '&:hover': {
                    background: 'rgba(226, 232, 240, 0.05)'
                  }
                }}
              >
                <ListItemIcon sx={{ color: selectedItem === item.id ? 'var(--aurora-violet)' : 'var(--silver)', minWidth: 40 }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    fontFamily: 'var(--font-body)',
                    fontSize: 14,
                    color: 'var(--silver)'
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>

        <Divider sx={{ borderColor: 'rgba(226, 232, 240, 0.1)', my: 1 }} />

        {/* Playlists Section */}
        <List sx={{ px: 1 }}>
          <ListItem disablePadding sx={{ mb: 0.5 }}>
            <ListItemButton
              onClick={() => setPlaylistsOpen(!playlistsOpen)}
              sx={{
                borderRadius: 'var(--radius-md)',
                '&:hover': {
                  background: 'rgba(226, 232, 240, 0.05)'
                }
              }}
            >
              <ListItemIcon sx={{ color: 'var(--silver)', minWidth: 40 }}>
                <PlaylistPlay />
              </ListItemIcon>
              <ListItemText
                primary="Playlists"
                primaryTypographyProps={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 14,
                  color: 'var(--silver)'
                }}
              />
              {playlistsOpen ? <ExpandLess /> : <ExpandMore />}
            </ListItemButton>
          </ListItem>

          <Collapse in={playlistsOpen} timeout="auto" unmountOnExit>
            <List component="div" disablePadding>
              {playlists.map((playlist) => (
                <ListItem key={playlist.id} disablePadding sx={{ mb: 0.5, pl: 2 }}>
                  <ListItemButton
                    selected={selectedItem === playlist.id}
                    onClick={() => handleItemClick(playlist.id)}
                    sx={{
                      borderRadius: 'var(--radius-md)',
                      minHeight: 40,
                      '&.Mui-selected': {
                        background: 'rgba(124, 58, 237, 0.2)',
                        borderLeft: '4px solid',
                        borderImage: 'var(--aurora-gradient) 1'
                      },
                      '&:hover': {
                        background: 'rgba(226, 232, 240, 0.05)'
                      }
                    }}
                  >
                    <ListItemText
                      primary={playlist.name}
                      primaryTypographyProps={{
                        fontFamily: 'var(--font-body)',
                        fontSize: 13,
                        color: 'var(--silver)'
                      }}
                    />
                  </ListItemButton>
                </ListItem>
              ))}
              <ListItem disablePadding sx={{ pl: 2, mt: 1 }}>
                <ListItemButton
                  sx={{
                    borderRadius: 'var(--radius-md)',
                    minHeight: 40,
                    '&:hover': {
                      background: 'rgba(226, 232, 240, 0.05)'
                    }
                  }}
                >
                  <ListItemIcon sx={{ color: 'var(--aurora-violet)', minWidth: 36 }}>
                    <Add />
                  </ListItemIcon>
                  <ListItemText
                    primary="New Playlist"
                    primaryTypographyProps={{
                      fontFamily: 'var(--font-body)',
                      fontSize: 13,
                      color: 'var(--aurora-violet)'
                    }}
                  />
                </ListItemButton>
              </ListItem>
            </List>
          </Collapse>
        </List>
      </Box>
    </Box>
  );
};

export default Sidebar;
