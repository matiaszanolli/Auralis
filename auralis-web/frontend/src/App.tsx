import React, { useState, useEffect } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Container,
  Grid,
  Card,
  CardContent,
  IconButton,
  Badge,
  Alert,
  Snackbar
} from '@mui/material';
import {
  LibraryMusic,
  QueueMusic,
  Search,
  FolderOpen,
  Settings,
  Dashboard,
  Equalizer,
  Menu as MenuIcon,
  Close as CloseIcon
} from '@mui/icons-material';

import LibraryView from './components/LibraryView';
import AudioPlayer from './components/AudioPlayer';
import StatusBar from './components/StatusBar';
import { useWebSocket } from './hooks/useWebSocket';
import { useLibraryStats } from './hooks/useLibraryStats';

const DRAWER_WIDTH = 280;

interface NavigationItem {
  id: string;
  label: string;
  icon: React.ReactElement;
  component?: React.ComponentType;
}

const navigationItems: NavigationItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: <Dashboard /> },
  { id: 'library', label: 'Library', icon: <LibraryMusic />, component: LibraryView },
  { id: 'playlists', label: 'Playlists', icon: <QueueMusic /> },
  { id: 'search', label: 'Search', icon: <Search /> },
  { id: 'scanner', label: 'File Scanner', icon: <FolderOpen /> },
  { id: 'equalizer', label: 'Audio Processing', icon: <Equalizer /> },
  { id: 'settings', label: 'Settings', icon: <Settings /> },
];

function App() {
  const [currentView, setCurrentView] = useState('library');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // WebSocket connection for real-time updates
  const { connected, lastMessage } = useWebSocket('ws://localhost:8000/ws');

  // Library statistics
  const { stats, isLoading: statsLoading, error: statsError } = useLibraryStats();

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      try {
        const message = JSON.parse(lastMessage);

        switch (message.type) {
          case 'scan_complete':
            setNotification({
              message: `Scan completed: ${message.data.files_added} files added`,
              type: 'success'
            });
            break;

          case 'scan_error':
            setNotification({
              message: `Scan failed: ${message.data.error}`,
              type: 'error'
            });
            break;
        }
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    }
  }, [lastMessage]);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleViewChange = (viewId: string) => {
    setCurrentView(viewId);
    setMobileOpen(false); // Close mobile drawer when navigating
  };

  const renderMainContent = () => {
    const currentItem = navigationItems.find(item => item.id === currentView);

    if (currentItem?.component) {
      const Component = currentItem.component;
      return <Component />;
    }

    // Default content for views without components yet
    return (
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Grid container spacing(3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h4" gutterBottom>
                  🎵 Welcome to Auralis Web
                </Typography>
                <Typography variant="body1" color="text.secondary" paragraph>
                  Professional audio mastering and library management in your browser.
                  This modern web interface replaces the old Tkinter GUI with a beautiful,
                  responsive, and cross-platform experience.
                </Typography>

                {stats && (
                  <Box sx={{ mt: 3 }}>
                    <Typography variant="h6" gutterBottom>
                      Library Statistics
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6} sm={3}>
                        <Card variant="outlined">
                          <CardContent sx={{ textAlign: 'center' }}>
                            <Typography variant="h4" color="primary">
                              {stats.total_tracks || 0}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Tracks
                            </Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Card variant="outlined">
                          <CardContent sx={{ textAlign: 'center' }}>
                            <Typography variant="h4" color="primary">
                              {stats.total_artists || 0}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Artists
                            </Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Card variant="outlined">
                          <CardContent sx={{ textAlign: 'center' }}>
                            <Typography variant="h4" color="primary">
                              {stats.total_albums || 0}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Albums
                            </Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Card variant="outlined">
                          <CardContent sx={{ textAlign: 'center' }}>
                            <Typography variant="h4" color="primary">
                              {(stats.total_filesize_gb || 0).toFixed(1)} GB
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Storage
                            </Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                    </Grid>
                  </Box>
                )}

                <Alert severity="info" sx={{ mt: 3 }}>
                  <Typography variant="body2">
                    Current view: <strong>{currentItem?.label || currentView}</strong>
                    {!currentItem?.component && " (Coming soon)"}
                  </Typography>
                </Alert>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Container>
    );
  };

  const drawer = (
    <Box>
      {/* Header */}
      <Toolbar sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
          🎵 Auralis
        </Typography>
        <IconButton
          color="inherit"
          aria-label="close drawer"
          edge="end"
          onClick={handleDrawerToggle}
          sx={{ display: { sm: 'none' } }}
        >
          <CloseIcon />
        </IconButton>
      </Toolbar>

      {/* Connection Status */}
      <Box sx={{ p: 2 }}>
        <Alert
          severity={connected ? "success" : "warning"}
          variant="outlined"
          sx={{ fontSize: '0.75rem' }}
        >
          {connected ? "🟢 Connected" : "🟡 Connecting..."}
        </Alert>
      </Box>

      {/* Navigation Items */}
      <List>
        {navigationItems.map((item) => (
          <ListItem
            button
            key={item.id}
            selected={currentView === item.id}
            onClick={() => handleViewChange(item.id)}
            sx={{
              '&.Mui-selected': {
                backgroundColor: 'primary.main',
                color: 'primary.contrastText',
                '&:hover': {
                  backgroundColor: 'primary.dark',
                },
                '& .MuiListItemIcon-root': {
                  color: 'primary.contrastText',
                },
              },
            }}
          >
            <ListItemIcon>
              {item.component ? (
                <Badge color="primary" variant="dot">
                  {item.icon}
                </Badge>
              ) : (
                item.icon
              )}
            </ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItem>
        ))}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { sm: `${DRAWER_WIDTH}px` },
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            {navigationItems.find(item => item.id === currentView)?.label || 'Auralis'}
          </Typography>
          {/* Add status indicators here */}
        </Toolbar>
      </AppBar>

      {/* Navigation Drawer */}
      <Box
        component="nav"
        sx={{ width: { sm: DRAWER_WIDTH }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: DRAWER_WIDTH },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: DRAWER_WIDTH },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Toolbar />
        <Box sx={{ flexGrow: 1 }}>
          {renderMainContent()}
        </Box>

        {/* Audio Player - Fixed at bottom */}
        <AudioPlayer />

        {/* Status Bar */}
        <StatusBar />
      </Box>

      {/* Notifications */}
      <Snackbar
        open={!!notification}
        autoHideDuration={6000}
        onClose={() => setNotification(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        {notification && (
          <Alert onClose={() => setNotification(null)} severity={notification.type}>
            {notification.message}
          </Alert>
        )}
      </Snackbar>
    </Box>
  );
}

export default App;