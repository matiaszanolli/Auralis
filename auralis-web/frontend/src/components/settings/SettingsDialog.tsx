import React, { useState, useEffect } from 'react';
import {
  DialogContent,
  DialogActions,
  Button,
  Box,
  IconButton,
  Typography
} from '@mui/material';
import {
  Close as CloseIcon,
  RestartAlt as ResetIcon
} from '@mui/icons-material';
import { settingsService, UserSettings, SettingsUpdate } from '../../services/settingsService';
import { StyledDialog, StyledDialogTitle } from '../library/Dialog.styles';
import { auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';
import { SettingsTabNav } from './SettingsTabNav';
import { LibrarySettingsPanel } from './LibrarySettingsPanel';
import { PlaybackSettingsPanel } from './PlaybackSettingsPanel';
import { AudioSettingsPanel } from './AudioSettingsPanel';
import { InterfaceSettingsPanel } from './InterfaceSettingsPanel';
import { EnhancementSettingsPanel } from './EnhancementSettingsPanel';
import { AdvancedSettingsPanel } from './AdvancedSettingsPanel';

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

      <SettingsTabNav activeTab={activeTab} onTabChange={(e, v) => setActiveTab(v)} />

      <DialogContent sx={{ p: 3, minHeight: 400 }}>
        {activeTab === 0 && (
          <LibrarySettingsPanel
            scanFolders={getValue('scan_folders')}
            autoScan={getValue('auto_scan')}
            scanInterval={getValue('scan_interval')}
            onSettingChange={handleSettingChange}
            onAddFolder={handleAddScanFolder}
            onRemoveFolder={handleRemoveScanFolder}
            onRescanFolder={handleRescanFolder}
          />
        )}

        {activeTab === 1 && (
          <PlaybackSettingsPanel
            gaplessEnabled={getValue('gapless_enabled')}
            crossfadeEnabled={getValue('crossfade_enabled')}
            crossfadeDuration={getValue('crossfade_duration')}
            replayGainEnabled={getValue('replay_gain_enabled')}
            volume={getValue('volume')}
            onSettingChange={handleSettingChange}
          />
        )}

        {activeTab === 2 && (
          <AudioSettingsPanel
            outputDevice={getValue('output_device')}
            bitDepth={getValue('bit_depth')}
            sampleRate={getValue('sample_rate')}
            onSettingChange={handleSettingChange}
          />
        )}

        {activeTab === 3 && (
          <InterfaceSettingsPanel
            theme={getValue('theme')}
            showVisualizations={getValue('show_visualizations')}
            miniPlayerOnClose={getValue('mini_player_on_close')}
            onSettingChange={handleSettingChange}
          />
        )}

        {activeTab === 4 && (
          <EnhancementSettingsPanel
            defaultPreset={getValue('default_preset')}
            autoEnhance={getValue('auto_enhance')}
            enhancementIntensity={getValue('enhancement_intensity')}
            onSettingChange={handleSettingChange}
          />
        )}

        {activeTab === 5 && (
          <AdvancedSettingsPanel
            cacheSize={getValue('cache_size')}
            maxConcurrentScans={getValue('max_concurrent_scans')}
            enableAnalytics={getValue('enable_analytics')}
            debugMode={getValue('debug_mode')}
            onSettingChange={handleSettingChange}
          />
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
