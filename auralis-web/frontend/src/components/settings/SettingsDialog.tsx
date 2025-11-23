import React, { useState, useEffect } from 'react';
import {
  DialogContent,
  DialogActions,
  Button,
  Tab,
  Box,
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
  ListItemSecondaryAction,
  Typography
} from '@mui/material';
import {
  Close as CloseIcon,
  Folder as FolderIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  RestartAlt as ResetIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { settingsService, UserSettings, SettingsUpdate } from '../../services/settingsService';
import { StyledDialog, StyledDialogTitle, StyledTabs, SectionContainer, SectionLabel, SectionDescription } from '../library/Dialog.styles';
import { auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  onSettingsChange?: (settings: UserSettings) => void;
}

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
            <SectionContainer>
              <SectionLabel>Scan Folders</SectionLabel>
              <SectionDescription>
                Folders to scan for music files. Use the native folder picker to select directories.
              </SectionDescription>
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
                    <FolderIcon sx={{ mr: 2, color: tokens.colors.accent.purple }} />
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
                  borderColor: tokens.colors.accent.purple,
                  color: tokens.colors.accent.purple,
                  '&:hover': {
                    borderColor: tokens.colors.accent.purple,
                    backgroundColor: auroraOpacity.standard
                  }
                }}
              >
                Add Folder
              </Button>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('auto_scan')}
                    onChange={(e) => handleSettingChange('auto_scan', e.target.checked)}
                  />
                }
                label="Auto-scan library"
              />
              <SectionDescription>
                Automatically scan for new files at regular intervals
              </SectionDescription>
            </SectionContainer>

            {getValue('auto_scan') && (
              <SectionContainer>
                <SectionLabel>Scan Interval (seconds)</SectionLabel>
                <TextField
                  type="number"
                  fullWidth
                  value={getValue('scan_interval')}
                  onChange={(e) => handleSettingChange('scan_interval', parseInt(e.target.value))}
                  inputProps={{ min: 60, max: 86400 }}
                />
              </SectionContainer>
            )}
          </Box>
        )}

        {/* Playback Settings */}
        {activeTab === 1 && (
          <Box>
            <SectionContainer>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('gapless_enabled')}
                    onChange={(e) => handleSettingChange('gapless_enabled', e.target.checked)}
                  />
                }
                label="Gapless playback"
              />
              <SectionDescription>
                Eliminate silence between tracks for seamless listening
              </SectionDescription>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('crossfade_enabled')}
                    onChange={(e) => handleSettingChange('crossfade_enabled', e.target.checked)}
                  />
                }
                label="Crossfade"
              />
              <SectionDescription>
                Smoothly transition between tracks
              </SectionDescription>
            </SectionContainer>

            {getValue('crossfade_enabled') && (
              <SectionContainer>
                <SectionLabel>Crossfade Duration: {getValue('crossfade_duration').toFixed(1)}s</SectionLabel>
                <Slider
                  value={getValue('crossfade_duration')}
                  onChange={(e, v) => handleSettingChange('crossfade_duration', v)}
                  min={0}
                  max={10}
                  step={0.5}
                  valueLabelDisplay="auto"
                />
              </SectionContainer>
            )}

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('replay_gain_enabled')}
                    onChange={(e) => handleSettingChange('replay_gain_enabled', e.target.checked)}
                  />
                }
                label="Replay Gain"
              />
              <SectionDescription>
                Normalize volume levels across tracks
              </SectionDescription>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <SectionLabel>Default Volume: {Math.round(getValue('volume') * 100)}%</SectionLabel>
              <Slider
                value={getValue('volume')}
                onChange={(e, v) => handleSettingChange('volume', v)}
                min={0}
                max={1}
                step={0.01}
                valueLabelDisplay="auto"
                valueLabelFormat={(v) => `${Math.round(v * 100)}%`}
              />
            </SectionContainer>
          </Box>
        )}

        {/* Audio Settings */}
        {activeTab === 2 && (
          <Box>
            <SectionContainer>
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
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
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
              <SectionDescription>
                Higher bit depth provides better dynamic range
              </SectionDescription>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
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
              <SectionDescription>
                Higher sample rates capture more audio detail
              </SectionDescription>
            </SectionContainer>
          </Box>
        )}

        {/* Interface Settings */}
        {activeTab === 3 && (
          <Box>
            <SectionContainer>
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
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('show_visualizations')}
                    onChange={(e) => handleSettingChange('show_visualizations', e.target.checked)}
                  />
                }
                label="Show visualizations"
              />
              <SectionDescription>
                Display audio visualizations and waveforms
              </SectionDescription>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('mini_player_on_close')}
                    onChange={(e) => handleSettingChange('mini_player_on_close', e.target.checked)}
                  />
                }
                label="Mini player on close"
              />
              <SectionDescription>
                Show mini player when closing main window
              </SectionDescription>
            </SectionContainer>
          </Box>
        )}

        {/* Enhancement Settings */}
        {activeTab === 4 && (
          <Box>
            <SectionContainer>
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
              <SectionDescription>
                Default audio enhancement preset for playback
              </SectionDescription>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('auto_enhance')}
                    onChange={(e) => handleSettingChange('auto_enhance', e.target.checked)}
                  />
                }
                label="Auto-enhance playback"
              />
              <SectionDescription>
                Automatically apply enhancement to all tracks
              </SectionDescription>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <SectionLabel>Enhancement Intensity: {Math.round(getValue('enhancement_intensity') * 100)}%</SectionLabel>
              <Slider
                value={getValue('enhancement_intensity')}
                onChange={(e, v) => handleSettingChange('enhancement_intensity', v)}
                min={0}
                max={1}
                step={0.1}
                valueLabelDisplay="auto"
                valueLabelFormat={(v) => `${Math.round(v * 100)}%`}
              />
              <SectionDescription>
                Adjust the strength of audio enhancement
              </SectionDescription>
            </SectionContainer>
          </Box>
        )}

        {/* Advanced Settings */}
        {activeTab === 5 && (
          <Box>
            <SectionContainer>
              <SectionLabel>Cache Size (MB)</SectionLabel>
              <TextField
                type="number"
                fullWidth
                value={getValue('cache_size')}
                onChange={(e) => handleSettingChange('cache_size', parseInt(e.target.value))}
                inputProps={{ min: 128, max: 8192 }}
              />
              <SectionDescription>
                Amount of disk space for processed audio cache
              </SectionDescription>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <SectionLabel>Max Concurrent Scans</SectionLabel>
              <TextField
                type="number"
                fullWidth
                value={getValue('max_concurrent_scans')}
                onChange={(e) => handleSettingChange('max_concurrent_scans', parseInt(e.target.value))}
                inputProps={{ min: 1, max: 16 }}
              />
              <SectionDescription>
                Number of parallel threads for library scanning
              </SectionDescription>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('enable_analytics')}
                    onChange={(e) => handleSettingChange('enable_analytics', e.target.checked)}
                  />
                }
                label="Enable analytics"
              />
              <SectionDescription>
                Collect anonymous usage data to improve Auralis
              </SectionDescription>
            </SectionContainer>

            <Divider sx={{ my: 3 }} />

            <SectionContainer>
              <FormControlLabel
                control={
                  <Switch
                    checked={getValue('debug_mode')}
                    onChange={(e) => handleSettingChange('debug_mode', e.target.checked)}
                  />
                }
                label="Debug mode"
              />
              <SectionDescription>
                Show detailed logging and diagnostic information
              </SectionDescription>
            </SectionContainer>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2, borderTop: `1px solid ${auroraOpacity.ultraLight}` }}>
        <Button onClick={handleReset} startIcon={<ResetIcon />} color="error">
          Reset to Defaults
        </Button>
        <Box sx={{ flex: 1 }} />
        <Button onClick={onClose} color="inherit">
          Cancel
        </Button>
        <Button onClick={handleSave} variant="contained" sx={{
          background: `linear-gradient(45deg, ${tokens.colors.accent.purple}, ${tokens.colors.accent.secondary})`,
          '&:hover': {
            background: `linear-gradient(45deg, ${tokens.colors.accent.purple}, ${tokens.colors.accent.secondary})`
          }
        }}>
          Save Changes
        </Button>
      </DialogActions>
    </StyledDialog>
  );
};

export default SettingsDialog;
