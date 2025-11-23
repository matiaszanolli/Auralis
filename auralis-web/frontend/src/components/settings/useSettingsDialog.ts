import { useState, useEffect, useCallback } from 'react';
import { settingsService, UserSettings, SettingsUpdate } from '../../services/settingsService';

export interface UseSettingsDialogProps {
  open: boolean;
  onSettingsChange?: (settings: UserSettings) => void;
}

/**
 * useSettingsDialog - Manages settings dialog state and operations
 *
 * Handles:
 * - Loading settings
 * - Tracking pending changes
 * - Saving settings
 * - Resetting to defaults
 * - Folder operations (add, remove, rescan)
 */
export const useSettingsDialog = ({ open, onSettingsChange }: UseSettingsDialogProps) => {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingChanges, setPendingChanges] = useState<SettingsUpdate>({});

  // Load settings when dialog opens
  useEffect(() => {
    if (open) {
      loadSettings();
    }
  }, [open]);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await settingsService.getSettings();
      setSettings(data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSettingChange = useCallback((key: keyof SettingsUpdate, value: any) => {
    setPendingChanges((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSave = useCallback(
    async (onClose: () => void) => {
      if (Object.keys(pendingChanges).length === 0) {
        onClose();
        return;
      }

      try {
        const result = await settingsService.updateSettings(pendingChanges);
        setSettings(result.settings);
        setPendingChanges({});
        onSettingsChange?.(result.settings);
        onClose();
      } catch (error) {
        console.error('Failed to save settings:', error);
      }
    },
    [pendingChanges, onSettingsChange]
  );

  const handleReset = useCallback(async () => {
    if (!window.confirm('Reset all settings to defaults?')) {
      return;
    }

    try {
      const result = await settingsService.resetSettings();
      setSettings(result.settings);
      setPendingChanges({});
      onSettingsChange?.(result.settings);
    } catch (error) {
      console.error('Failed to reset settings:', error);
    }
  }, [onSettingsChange]);

  const triggerScan = useCallback(async (directory: string) => {
    try {
      const response = await fetch('/api/library/scan', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ directory }),
      });

      if (response.ok) {
        console.log(`Scan started for: ${directory}`);
      }
    } catch (error) {
      console.error('Failed to trigger scan:', error);
    }
  }, []);

  const handleAddScanFolder = useCallback(async () => {
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
      onSettingsChange?.(result.settings);

      // Trigger scan of the newly added folder
      await triggerScan(folder);
    } catch (error) {
      console.error('Failed to add scan folder:', error);
    }
  }, [triggerScan, onSettingsChange]);

  const handleRemoveScanFolder = useCallback(
    async (folder: string) => {
      if (
        !window.confirm(
          `Remove folder from library?\n\n${folder}\n\nNote: Files will remain on disk.`
        )
      ) {
        return;
      }

      try {
        const result = await settingsService.removeScanFolder(folder);
        setSettings(result.settings);
        onSettingsChange?.(result.settings);
      } catch (error) {
        console.error('Failed to remove scan folder:', error);
      }
    },
    [onSettingsChange]
  );

  const handleRescanFolder = useCallback(
    async (folder: string) => {
      await triggerScan(folder);
    },
    [triggerScan]
  );

  const getValue = useCallback(
    <K extends keyof SettingsUpdate>(key: K): any => {
      if (key in pendingChanges) {
        return pendingChanges[key as keyof SettingsUpdate];
      }
      return settings ? (settings[key as keyof UserSettings] as any) : null;
    },
    [settings, pendingChanges]
  );

  return {
    settings,
    loading,
    pendingChanges,
    handleSettingChange,
    handleSave,
    handleReset,
    handleAddScanFolder,
    handleRemoveScanFolder,
    handleRescanFolder,
    getValue,
  };
};
