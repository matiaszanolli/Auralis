import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Tabs,
  Tab,
  Box,
  Typography,
  Switch,
  FormControlLabel,
  TextField,
  Slider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction
} from '@mui/material';
import {
  Close as CloseIcon,
  Folder as FolderIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  RestartAlt as ResetIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { settingsService, UserSettings, SettingsUpdate } from '../../services/settingsService';

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  onSettingsChange?: (settings: UserSettings) => void;
}

// Styled components
const StyledDialog = styled(Dialog)(({ theme }) => ({
  '& .MuiDialog-paper': {
    background: 'rgba(26, 31, 58, 0.98)',
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: theme.spacing(2),
    minWidth: 700,
    maxWidth: 900,
    minHeight: 600
  }
}));

const StyledDialogTitle = styled(DialogTitle)(({ theme }) => ({
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  color: 'white',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: theme.spacing(2, 3)
}));

const StyledTabs = styled(Tabs)(({ theme }) => ({
  borderBottom: '1px solid rgba(255,255,255,0.1)',
  minHeight: 48,
  '& .MuiTab-root': {
    textTransform: 'none',
    fontSize: '0.95rem',
    minHeight: 48,
    color: theme.palette.text.secondary,
    '&.Mui-selected': {
      color: '#667eea'
    }
  },
  '& .MuiTabs-indicator': {
    backgroundColor: '#667eea'
  }
}));

const SettingSection = styled(Box)(({ theme }) => ({
  marginBottom: theme.spacing(3)
}));

const SettingLabel = styled(Typography)(({ theme }) => ({
  fontSize: '0.875rem',
  fontWeight: 600,
  color: theme.palette.text.primary,
  marginBottom: theme.spacing(1)
}));

const SettingDescription = styled(Typography)(({ theme }) => ({
  fontSize: '0.75rem',
  color: theme.palette.text.secondary,
  marginTop: theme.spacing(0.5)
}));

export const SettingsDialog: React.FC<SettingsDialogProps> = ({ open, onClose, onSettingsChange }) => {
  const [activeTab, setActiveTab] = useState(0);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingChanges, setPendingChanges] = useState<SettingsUpdate>({});

  useEffect(() => {
    if (open) {
      loadSettings();
    }
  }, [open]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await settingsService.getSettings();
      setSettings(data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSettingChange = (key: keyof SettingsUpdate, value: any) => {
    setPendingChanges((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    if (Object.keys(pendingChanges).length === 0) {
      onClose();
      return;
    }

    try {
      const result = await settingsService.updateSettings(pendingChanges);
      setSettings(result.settings);
      setPendingChanges({});
      if (onSettingsChange) {
        onSettingsChange(result.settings);
      }
      onClose();
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset all settings to defaults?')) {
      return;
    }

    try {
      const result = await settingsService.resetSettings();
      setSettings(result.settings);
      setPendingChanges({});
      if (onSettingsChange) {
        onSettingsChange(result.settings);
      }
    } catch (error) {
      console.error('Failed to reset settings:', error);
    }
  };

  const triggerScan = async (directory: string) => {
    try {
      const response = await fetch('/api/library/scan', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ directory })
      });

      if (response.ok) {
        console.log(`Scan started for: ${directory}`);
      }
    } catch (error) {
      console.error('Failed to trigger scan:', error);
    }
  };

  const handleAddScanFolder = async () => {
    let folder: string | null = null;

    // Use Electron folder picker if available
    if ((window as any).electronAPI && (window as any).electronAPI.selectFolder) {
      try {
        folder = await (window as any).electronAPI.selectFolder();
      } catch (error) {
        console.error('Electron folder picker failed:', error);
      }
    }

    // Fallback to prompt for web
    if (!folder) {
      folder = prompt('Enter folder path:');
    }

    if (!folder) return;

    try {
      const result = await settingsService.addScanFolder(folder);
      setSettings(result.settings);
      if (onSettingsChange) {
        onSettingsChange(result.settings);
      }

      // Trigger scan of the newly added folder
      await triggerScan(folder);
    } catch (error) {
      console.error('Failed to add scan folder:', error);
    }
  };

  const handleRemoveScanFolder = async (folder: string) => {
    if (!window.confirm(`Remove folder from library?\n\n${folder}\n\nNote: Files will remain on disk.`)) {
      return;
    }

    try {
      const result = await settingsService.removeScanFolder(folder);
      setSettings(result.settings);
      if (onSettingsChange) {
        onSettingsChange(result.settings);
      }
    } catch (error) {
      console.error('Failed to remove scan folder:', error);
    }
  };

  const handleRescanFolder = async (folder: string) => {
    await triggerScan(folder);
  };

  const getValue = <K extends keyof SettingsUpdate>(key: K): any => {
    if (key in pendingChanges) {
      return pendingChanges[key as keyof SettingsUpdate];
    }
    return settings ? (settings[key as keyof UserSettings] as any) : null;
  };

  if (!settings) {
    return null;
  }

  return (
    <StyledDialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <StyledDialogTitle>
        <Typography variant="h6" component="span">Settings</Typography>
        <IconButton onClick={onClose} sx={{ color: 'white' }}>
          <CloseIcon />
        </IconButton>
      </StyledDialogTitle>

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <StyledTabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
          <Tab label="Library" />
          <Tab label="Playback" />
          <Tab label="Audio" />
          <Tab label="Interface" />
          <Tab label="Enhancement" />
          <Tab label="Advanced" />
        </StyledTabs>
      </Box>

      <DialogContent sx={{ p: 3, minHeight: 400 }}>
        {/* Library Settings */}
        {activeTab === 0 && (
          <Box>
            <SettingSection>
              <SettingLabel>Scan Folders</SettingLabel>
              <SettingDescription>
                Folders to scan for music files. Use the native folder picker to select directories.
              </SettingDescription>
              <List>
                {getValue('scan_folders').length === 0 && (
                  <ListItem sx={{ px: 0 }}>
                    <ListItemText
                      primary="No folders added yet"
                      secondary="Click 'Add Folder' below to start building your library"
                      primaryTypographyProps={{ color: 'text.secondary' }}
                    />
                  </ListItem>
                )}
                {getValue('scan_folders').map((folder: string, index: number) => (
                  <ListItem key={index} sx={{ px: 0, py: 1 }}>
                    <FolderIcon sx={{ mr: 2, color: '#667eea' }} />
                    <ListItemText
                      primary={folder}
                      primaryTypographyProps={{ fontSize: '0.9rem' }}
                    />
                    <ListItemSecondaryAction>
                      <IconButton
                        onClick={() => handleRescanFolder(folder)}
                        size="small"
                        sx={{ mr: 1 }}
                        title="Rescan this folder"
                      >
                        <RefreshIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        onClick={() => handleRemoveScanFolder(folder)}
                        size="small"
                        color="error"
                        title="Remove this folder"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
              <Button
                startIcon={<AddIcon />}
                onClick={handleAddScanFolder}
                variant="outlined"
                sx={{
                  borderColor: '#667eea',
                  color: '#667eea',
                  '&:hover': {
                    borderColor: '#5568d3',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)'
                  }
                }}
              >
                Add Folder
              </Button>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('auto_scan')}
                    onChange={(e) => handleSettingChange('auto_scan', e.target.checked)}
                  />
                }
                label="Auto-scan library"
              />
              <SettingDescription>
                Automatically scan for new files at regular intervals
              </SettingDescription>
            </SettingSection>

            {getValue('auto_scan') && (
              <SettingSection>
                <SettingLabel>Scan Interval (seconds)</SettingLabel>
                <TextField
                  type="number"
                  fullWidth
                  value={getValue('scan_interval')}
                  onChange={(e) => handleSettingChange('scan_interval', parseInt(e.target.value))}
                  inputProps={{ min: 60, max: 86400 }}
                />
              </SettingSection>
            )}
          </Box>
        )}

        {/* Playback Settings */}
        {activeTab === 1 && (
          <Box>
            <SettingSection>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('gapless_enabled')}
                    onChange={(e) => handleSettingChange('gapless_enabled', e.target.checked)}
                  />
                }
                label="Gapless playback"
              />
              <SettingDescription>
                Eliminate silence between tracks for seamless listening
              </SettingDescription>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('crossfade_enabled')}
                    onChange={(e) => handleSettingChange('crossfade_enabled', e.target.checked)}
                  />
                }
                label="Crossfade"
              />
              <SettingDescription>
                Smoothly transition between tracks
              </SettingDescription>
            </SettingSection>

            {getValue('crossfade_enabled') && (
              <SettingSection>
                <SettingLabel>Crossfade Duration: {getValue('crossfade_duration').toFixed(1)}s</SettingLabel>
                <Slider
                  value={getValue('crossfade_duration')}
                  onChange={(e, v) => handleSettingChange('crossfade_duration', v)}
                  min={0}
                  max={10}
                  step={0.5}
                  valueLabelDisplay="auto"
                />
              </SettingSection>
            )}

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('replay_gain_enabled')}
                    onChange={(e) => handleSettingChange('replay_gain_enabled', e.target.checked)}
                  />
                }
                label="Replay Gain"
              />
              <SettingDescription>
                Normalize volume levels across tracks
              </SettingDescription>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <SettingLabel>Default Volume: {Math.round(getValue('volume') * 100)}%</SettingLabel>
              <Slider
                value={getValue('volume')}
                onChange={(e, v) => handleSettingChange('volume', v)}
                min={0}
                max={1}
                step={0.01}
                valueLabelDisplay="auto"
                valueLabelFormat={(v) => `${Math.round(v * 100)}%`}
              />
            </SettingSection>
          </Box>
        )}

        {/* Audio Settings */}
        {activeTab === 2 && (
          <Box>
            <SettingSection>
              <FormControl fullWidth>
                <InputLabel>Output Device</InputLabel>
                <Select
                  value={getValue('output_device')}
                  onChange={(e) => handleSettingChange('output_device', e.target.value)}
                  label="Output Device"
                >
                  <MenuItem value="default">Default</MenuItem>
                  {/* Add more devices here when available */}
                </Select>
              </FormControl>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControl fullWidth>
                <InputLabel>Bit Depth</InputLabel>
                <Select
                  value={getValue('bit_depth')}
                  onChange={(e) => handleSettingChange('bit_depth', e.target.value)}
                  label="Bit Depth"
                >
                  <MenuItem value={16}>16-bit</MenuItem>
                  <MenuItem value={24}>24-bit</MenuItem>
                  <MenuItem value={32}>32-bit</MenuItem>
                </Select>
              </FormControl>
              <SettingDescription>
                Higher bit depth provides better dynamic range
              </SettingDescription>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControl fullWidth>
                <InputLabel>Sample Rate</InputLabel>
                <Select
                  value={getValue('sample_rate')}
                  onChange={(e) => handleSettingChange('sample_rate', e.target.value)}
                  label="Sample Rate"
                >
                  <MenuItem value={44100}>44.1 kHz (CD Quality)</MenuItem>
                  <MenuItem value={48000}>48 kHz (Studio)</MenuItem>
                  <MenuItem value={96000}>96 kHz (Hi-Res)</MenuItem>
                  <MenuItem value={192000}>192 kHz (Ultra Hi-Res)</MenuItem>
                </Select>
              </FormControl>
              <SettingDescription>
                Higher sample rates capture more audio detail
              </SettingDescription>
            </SettingSection>
          </Box>
        )}

        {/* Interface Settings */}
        {activeTab === 3 && (
          <Box>
            <SettingSection>
              <FormControl fullWidth>
                <InputLabel>Theme</InputLabel>
                <Select
                  value={getValue('theme')}
                  onChange={(e) => handleSettingChange('theme', e.target.value)}
                  label="Theme"
                >
                  <MenuItem value="dark">Dark</MenuItem>
                  <MenuItem value="light">Light</MenuItem>
                </Select>
              </FormControl>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('show_visualizations')}
                    onChange={(e) => handleSettingChange('show_visualizations', e.target.checked)}
                  />
                }
                label="Show visualizations"
              />
              <SettingDescription>
                Display audio visualizations and waveforms
              </SettingDescription>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('mini_player_on_close')}
                    onChange={(e) => handleSettingChange('mini_player_on_close', e.target.checked)}
                  />
                }
                label="Mini player on close"
              />
              <SettingDescription>
                Show mini player when closing main window
              </SettingDescription>
            </SettingSection>
          </Box>
        )}

        {/* Enhancement Settings */}
        {activeTab === 4 && (
          <Box>
            <SettingSection>
              <FormControl fullWidth>
                <InputLabel>Default Preset</InputLabel>
                <Select
                  value={getValue('default_preset')}
                  onChange={(e) => handleSettingChange('default_preset', e.target.value)}
                  label="Default Preset"
                >
                  <MenuItem value="adaptive">Adaptive</MenuItem>
                  <MenuItem value="gentle">Gentle</MenuItem>
                  <MenuItem value="warm">Warm</MenuItem>
                  <MenuItem value="bright">Bright</MenuItem>
                  <MenuItem value="punchy">Punchy</MenuItem>
                </Select>
              </FormControl>
              <SettingDescription>
                Default audio enhancement preset for playback
              </SettingDescription>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('auto_enhance')}
                    onChange={(e) => handleSettingChange('auto_enhance', e.target.checked)}
                  />
                }
                label="Auto-enhance playback"
              />
              <SettingDescription>
                Automatically apply enhancement to all tracks
              </SettingDescription>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <SettingLabel>Enhancement Intensity: {Math.round(getValue('enhancement_intensity') * 100)}%</SettingLabel>
              <Slider
                value={getValue('enhancement_intensity')}
                onChange={(e, v) => handleSettingChange('enhancement_intensity', v)}
                min={0}
                max={1}
                step={0.1}
                valueLabelDisplay="auto"
                valueLabelFormat={(v) => `${Math.round(v * 100)}%`}
              />
              <SettingDescription>
                Adjust the strength of audio enhancement
              </SettingDescription>
            </SettingSection>
          </Box>
        )}

        {/* Advanced Settings */}
        {activeTab === 5 && (
          <Box>
            <SettingSection>
              <SettingLabel>Cache Size (MB)</SettingLabel>
              <TextField
                type="number"
                fullWidth
                value={getValue('cache_size')}
                onChange={(e) => handleSettingChange('cache_size', parseInt(e.target.value))}
                inputProps={{ min: 128, max: 8192 }}
              />
              <SettingDescription>
                Amount of disk space for processed audio cache
              </SettingDescription>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <SettingLabel>Max Concurrent Scans</SettingLabel>
              <TextField
                type="number"
                fullWidth
                value={getValue('max_concurrent_scans')}
                onChange={(e) => handleSettingChange('max_concurrent_scans', parseInt(e.target.value))}
                inputProps={{ min: 1, max: 16 }}
              />
              <SettingDescription>
                Number of parallel threads for library scanning
              </SettingDescription>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('enable_analytics')}
                    onChange={(e) => handleSettingChange('enable_analytics', e.target.checked)}
                  />
                }
                label="Enable analytics"
              />
              <SettingDescription>
                Collect anonymous usage data to improve Auralis
              </SettingDescription>
            </SettingSection>

            <Divider sx={{ my: 3 }} />

            <SettingSection>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('debug_mode')}
                    onChange={(e) => handleSettingChange('debug_mode', e.target.checked)}
                  />
                }
                label="Debug mode"
              />
              <SettingDescription>
                Show detailed logging and diagnostic information
              </SettingDescription>
            </SettingSection>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
        <Button onClick={handleReset} startIcon={<ResetIcon />} color="error">
          Reset to Defaults
        </Button>
        <Box sx={{ flex: 1 }} />
        <Button onClick={onClose} color="inherit">
          Cancel
        </Button>
        <Button onClick={handleSave} variant="contained" sx={{
          background: 'linear-gradient(45deg, #667eea, #764ba2)',
          '&:hover': {
            background: 'linear-gradient(45deg, #5568d3, #6a3f8f)'
          }
        }}>
          Save Changes
        </Button>
      </DialogActions>
    </StyledDialog>
  );
};

export default SettingsDialog;
