/**
 * Tests for Settings Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the user settings management service
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import settingsService, { type UserSettings, type SettingsUpdate } from '../settingsService';

// Mock fetch
global.fetch = vi.fn();

const mockSettings: UserSettings = {
  id: 1,
  // Library
  scan_folders: ['/music'],
  file_types: ['mp3', 'flac', 'wav'],
  auto_scan: true,
  scan_interval: 3600,
  // Playback
  crossfade_enabled: true,
  crossfade_duration: 2.0,
  gapless_enabled: true,
  replay_gain_enabled: false,
  volume: 0.8,
  // Audio
  output_device: 'default',
  bit_depth: 16,
  sample_rate: 44100,
  // Interface
  theme: 'dark',
  language: 'en',
  show_visualizations: true,
  mini_player_on_close: false,
  // Enhancement
  default_preset: 'adaptive',
  auto_enhance: true,
  enhancement_intensity: 0.7,
  // Advanced
  cache_size: 1024,
  max_concurrent_scans: 4,
  enable_analytics: false,
  debug_mode: false,
  // Timestamps
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

describe('SettingsService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getSettings', () => {
    it('should get current settings successfully', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      });

      const result = await settingsService.getSettings();

      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8765/api/settings');
      expect(result).toEqual(mockSettings);
    });

    it('should throw error on failed fetch', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

      await expect(settingsService.getSettings()).rejects.toThrow('Failed to get settings');
    });

    it('should handle network errors', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

      await expect(settingsService.getSettings()).rejects.toThrow('Network error');
    });

    it('should return valid settings structure', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      });

      const result = await settingsService.getSettings();

      // Verify all required fields exist
      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('scan_folders');
      expect(result).toHaveProperty('theme');
      expect(result).toHaveProperty('default_preset');
      expect(result).toHaveProperty('created_at');
      expect(result).toHaveProperty('updated_at');
    });
  });

  describe('updateSettings', () => {
    it('should update settings successfully', async () => {
      const updates: SettingsUpdate = {
        theme: 'light',
        volume: 0.9,
      };

      const expectedResponse = {
        message: 'Settings updated',
        settings: { ...mockSettings, ...updates },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => expectedResponse,
      });

      const result = await settingsService.updateSettings(updates);

      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8765/api/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });
      expect(result).toEqual(expectedResponse);
    });

    it('should update single field', async () => {
      const updates: SettingsUpdate = { volume: 0.5 };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Updated', settings: mockSettings }),
      });

      await settingsService.updateSettings(updates);

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8765/api/settings',
        expect.objectContaining({
          body: JSON.stringify({ volume: 0.5 }),
        })
      );
    });

    it('should update multiple fields', async () => {
      const updates: SettingsUpdate = {
        theme: 'light',
        language: 'es',
        volume: 0.9,
        crossfade_enabled: false,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Updated', settings: mockSettings }),
      });

      await settingsService.updateSettings(updates);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body).toEqual(updates);
    });

    it('should throw error on failed update', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

      await expect(settingsService.updateSettings({ volume: 0.5 })).rejects.toThrow(
        'Failed to update settings'
      );
    });

    it('should handle invalid values', async () => {
      const updates: SettingsUpdate = { volume: 999 }; // Invalid volume

      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 400,
      });

      await expect(settingsService.updateSettings(updates)).rejects.toThrow();
    });

    it('should update library settings', async () => {
      const updates: SettingsUpdate = {
        auto_scan: false,
        scan_interval: 7200,
        file_types: ['flac', 'wav', 'mp3', 'm4a'],
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Updated', settings: mockSettings }),
      });

      await settingsService.updateSettings(updates);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.auto_scan).toBe(false);
      expect(body.scan_interval).toBe(7200);
      expect(body.file_types).toHaveLength(4);
    });

    it('should update playback settings', async () => {
      const updates: SettingsUpdate = {
        crossfade_enabled: true,
        crossfade_duration: 3.5,
        gapless_enabled: false,
        replay_gain_enabled: true,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Updated', settings: mockSettings }),
      });

      await settingsService.updateSettings(updates);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.crossfade_enabled).toBe(true);
      expect(body.crossfade_duration).toBe(3.5);
    });

    it('should update enhancement settings', async () => {
      const updates: SettingsUpdate = {
        default_preset: 'warm',
        auto_enhance: false,
        enhancement_intensity: 0.5,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Updated', settings: mockSettings }),
      });

      await settingsService.updateSettings(updates);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.default_preset).toBe('warm');
      expect(body.auto_enhance).toBe(false);
      expect(body.enhancement_intensity).toBe(0.5);
    });
  });

  describe('resetSettings', () => {
    it('should reset settings to defaults', async () => {
      const defaultSettings = {
        message: 'Settings reset to defaults',
        settings: mockSettings,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => defaultSettings,
      });

      const result = await settingsService.resetSettings();

      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8765/api/settings/reset', {
        method: 'POST',
      });
      expect(result).toEqual(defaultSettings);
    });

    it('should throw error on failed reset', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

      await expect(settingsService.resetSettings()).rejects.toThrow('Failed to reset settings');
    });

    it('should handle server errors during reset', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(settingsService.resetSettings()).rejects.toThrow();
    });
  });

  describe('addScanFolder', () => {
    it('should add scan folder successfully', async () => {
      const folder = '/music/jazz';
      const expectedResponse = {
        message: 'Scan folder added',
        settings: {
          ...mockSettings,
          scan_folders: [...mockSettings.scan_folders, folder],
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => expectedResponse,
      });

      const result = await settingsService.addScanFolder(folder);

      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8765/api/settings/scan-folders', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ folder }),
      });
      expect(result).toEqual(expectedResponse);
    });

    it('should add multiple different folders', async () => {
      const folders = ['/music/rock', '/music/classical', '/music/jazz'];

      for (const folder of folders) {
        (global.fetch as any).mockResolvedValueOnce({
          ok: true,
          json: async () => ({ message: 'Added', settings: mockSettings }),
        });

        await settingsService.addScanFolder(folder);
      }

      expect(global.fetch).toHaveBeenCalledTimes(3);
    });

    it('should throw error on failed add', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

      await expect(settingsService.addScanFolder('/invalid')).rejects.toThrow(
        'Failed to add scan folder'
      );
    });

    it('should handle duplicate folder errors', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 409, // Conflict
      });

      await expect(settingsService.addScanFolder('/music')).rejects.toThrow();
    });

    it('should handle path with spaces', async () => {
      const folder = '/music/My Collection/Jazz';

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Added', settings: mockSettings }),
      });

      await settingsService.addScanFolder(folder);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.folder).toBe(folder);
    });

    it('should handle Windows paths', async () => {
      const folder = 'C:\\Music\\Collection';

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Added', settings: mockSettings }),
      });

      await settingsService.addScanFolder(folder);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.folder).toBe(folder);
    });
  });

  describe('removeScanFolder', () => {
    it('should remove scan folder successfully', async () => {
      const folder = '/music';
      const expectedResponse = {
        message: 'Scan folder removed',
        settings: {
          ...mockSettings,
          scan_folders: [],
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => expectedResponse,
      });

      const result = await settingsService.removeScanFolder(folder);

      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8765/api/settings/scan-folders', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ folder }),
      });
      expect(result).toEqual(expectedResponse);
    });

    it('should throw error on failed remove', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

      await expect(settingsService.removeScanFolder('/music')).rejects.toThrow(
        'Failed to remove scan folder'
      );
    });

    it('should handle removing non-existent folder', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      await expect(settingsService.removeScanFolder('/nonexistent')).rejects.toThrow();
    });

    it('should handle path with special characters', async () => {
      const folder = '/music/[Jazz] Collection';

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Removed', settings: mockSettings }),
      });

      await settingsService.removeScanFolder(folder);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.folder).toBe(folder);
    });
  });

  describe('Integration scenarios', () => {
    it('should handle complete settings workflow', async () => {
      // Get settings
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      });

      const settings = await settingsService.getSettings();
      expect(settings.theme).toBe('dark');

      // Update theme
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          message: 'Updated',
          settings: { ...mockSettings, theme: 'light' },
        }),
      });

      await settingsService.updateSettings({ theme: 'light' });

      // Reset settings
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Reset', settings: mockSettings }),
      });

      await settingsService.resetSettings();
    });

    it('should handle scan folder workflow', async () => {
      // Add folder
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Added', settings: mockSettings }),
      });

      await settingsService.addScanFolder('/music/new');

      // Remove folder
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Removed', settings: mockSettings }),
      });

      await settingsService.removeScanFolder('/music/new');
    });

    it('should handle multiple concurrent updates', async () => {
      const updates = [
        { theme: 'light' },
        { volume: 0.9 },
        { crossfade_enabled: false },
      ];

      const promises = updates.map(update => {
        (global.fetch as any).mockResolvedValueOnce({
          ok: true,
          json: async () => ({ message: 'Updated', settings: mockSettings }),
        });
        return settingsService.updateSettings(update);
      });

      const results = await Promise.all(promises);

      expect(results).toHaveLength(3);
      expect(global.fetch).toHaveBeenCalledTimes(3);
    });
  });

  describe('Error handling edge cases', () => {
    it('should handle malformed JSON response', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => { throw new Error('Invalid JSON'); },
      });

      await expect(settingsService.getSettings()).rejects.toThrow();
    });

    it('should handle null response', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => null,
      });

      const result = await settingsService.getSettings();
      expect(result).toBeNull();
    });

    it('should handle empty updates', async () => {
      const updates: SettingsUpdate = {};

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'No changes', settings: mockSettings }),
      });

      await settingsService.updateSettings(updates);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body).toEqual({});
    });

    it('should handle timeout errors', async () => {
      (global.fetch as any).mockImplementationOnce(() =>
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Timeout')), 100)
        )
      );

      await expect(settingsService.getSettings()).rejects.toThrow('Timeout');
    });

    it('should handle 401 unauthorized errors', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      await expect(settingsService.getSettings()).rejects.toThrow();
    });

    it('should handle 403 forbidden errors', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 403,
      });

      await expect(settingsService.updateSettings({ debug_mode: true })).rejects.toThrow();
    });
  });
});
