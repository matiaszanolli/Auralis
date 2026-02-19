/**
 * Tests for Settings Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the user settings management service.
 * Mocks at the apiRequest module level to avoid MSW conflicts.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../utils/apiRequest', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  APIRequestError: class APIRequestError extends Error {
    constructor(message: string, public statusCode: number, public detail?: string) {
      super(message);
      this.name = 'APIRequestError';
    }
  },
}));

import { get, post, put } from '../../utils/apiRequest';
import settingsService, { type UserSettings, type SettingsUpdate } from '../settingsService';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;
const mockPut = put as ReturnType<typeof vi.fn>;

const mockSettings: UserSettings = {
  id: 1,
  scan_folders: ['/music'],
  file_types: ['mp3', 'flac', 'wav'],
  auto_scan: true,
  scan_interval: 3600,
  crossfade_enabled: true,
  crossfade_duration: 2.0,
  gapless_enabled: true,
  replay_gain_enabled: false,
  volume: 0.8,
  output_device: 'default',
  bit_depth: 16,
  sample_rate: 44100,
  theme: 'dark',
  language: 'en',
  show_visualizations: true,
  mini_player_on_close: false,
  default_preset: 'adaptive',
  auto_enhance: true,
  enhancement_intensity: 0.7,
  cache_size: 1024,
  max_concurrent_scans: 4,
  enable_analytics: false,
  debug_mode: false,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

describe('SettingsService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getSettings', () => {
    it('should get current settings successfully', async () => {
      mockGet.mockResolvedValueOnce([mockSettings]);

      const result = await settingsService.getSettings();

      expect(mockGet).toHaveBeenCalledWith('/api/settings');
      expect(result).toEqual(mockSettings);
    });

    it('should throw when no settings are returned', async () => {
      mockGet.mockResolvedValueOnce([]);

      await expect(settingsService.getSettings()).rejects.toThrow('No settings found');
    });

    it('should return valid settings structure', async () => {
      mockGet.mockResolvedValueOnce([mockSettings]);

      const result = await settingsService.getSettings();

      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('scan_folders');
      expect(result).toHaveProperty('theme');
      expect(result).toHaveProperty('default_preset');
      expect(result).toHaveProperty('created_at');
      expect(result).toHaveProperty('updated_at');
    });

    it('should propagate network errors', async () => {
      mockGet.mockRejectedValueOnce(new Error('Network error'));

      await expect(settingsService.getSettings()).rejects.toThrow('Network error');
    });
  });

  describe('updateSettings', () => {
    it('should update settings successfully', async () => {
      const updates: SettingsUpdate = { theme: 'light', volume: 0.9 };
      const expectedResponse = { message: 'Settings updated', settings: { ...mockSettings, ...updates } };
      mockPut.mockResolvedValueOnce(expectedResponse);

      const result = await settingsService.updateSettings(updates);

      expect(mockPut).toHaveBeenCalledWith('/api/settings', updates);
      expect(result).toEqual(expectedResponse);
    });

    it('should update single field', async () => {
      const updates: SettingsUpdate = { volume: 0.5 };
      mockPut.mockResolvedValueOnce({ message: 'Updated', settings: mockSettings });

      await settingsService.updateSettings(updates);

      expect(mockPut).toHaveBeenCalledWith('/api/settings', { volume: 0.5 });
    });

    it('should update library settings', async () => {
      const updates: SettingsUpdate = {
        auto_scan: false,
        scan_interval: 7200,
        file_types: ['flac', 'wav', 'mp3', 'm4a'],
      };
      mockPut.mockResolvedValueOnce({ message: 'Updated', settings: mockSettings });

      await settingsService.updateSettings(updates);

      const callArg = mockPut.mock.calls[0][1];
      expect(callArg.auto_scan).toBe(false);
      expect(callArg.scan_interval).toBe(7200);
      expect(callArg.file_types).toHaveLength(4);
    });

    it('should update playback settings', async () => {
      const updates: SettingsUpdate = {
        crossfade_enabled: true,
        crossfade_duration: 3.5,
        gapless_enabled: false,
        replay_gain_enabled: true,
      };
      mockPut.mockResolvedValueOnce({ message: 'Updated', settings: mockSettings });

      await settingsService.updateSettings(updates);

      const callArg = mockPut.mock.calls[0][1];
      expect(callArg.crossfade_enabled).toBe(true);
      expect(callArg.crossfade_duration).toBe(3.5);
    });

    it('should update enhancement settings', async () => {
      const updates: SettingsUpdate = {
        default_preset: 'warm',
        auto_enhance: false,
        enhancement_intensity: 0.5,
      };
      mockPut.mockResolvedValueOnce({ message: 'Updated', settings: mockSettings });

      await settingsService.updateSettings(updates);

      const callArg = mockPut.mock.calls[0][1];
      expect(callArg.default_preset).toBe('warm');
      expect(callArg.auto_enhance).toBe(false);
      expect(callArg.enhancement_intensity).toBe(0.5);
    });

    it('should propagate errors', async () => {
      mockPut.mockRejectedValueOnce(new Error('Update failed'));

      await expect(settingsService.updateSettings({ volume: 0.5 })).rejects.toThrow('Update failed');
    });
  });

  describe('resetSettings', () => {
    it('should reset settings to defaults', async () => {
      const defaultResponse = { message: 'Settings reset to defaults', settings: mockSettings };
      mockPost.mockResolvedValueOnce(defaultResponse);

      const result = await settingsService.resetSettings();

      expect(mockPost).toHaveBeenCalledWith('/api/settings/reset', {});
      expect(result).toEqual(defaultResponse);
    });

    it('should propagate errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Reset failed'));

      await expect(settingsService.resetSettings()).rejects.toThrow('Reset failed');
    });
  });

  describe('addScanFolder', () => {
    it('should add scan folder successfully', async () => {
      const folder = '/music/jazz';
      const expectedResponse = {
        message: 'Scan folder added',
        settings: { ...mockSettings, scan_folders: [...mockSettings.scan_folders, folder] },
      };
      mockPost.mockResolvedValueOnce(expectedResponse);

      const result = await settingsService.addScanFolder(folder);

      expect(mockPost).toHaveBeenCalledWith('/api/settings/scan-folders', { folder });
      expect(result).toEqual(expectedResponse);
    });

    it('should handle path with spaces', async () => {
      const folder = '/music/My Collection/Jazz';
      mockPost.mockResolvedValueOnce({ message: 'Added', settings: mockSettings });

      await settingsService.addScanFolder(folder);

      expect(mockPost).toHaveBeenCalledWith('/api/settings/scan-folders', { folder });
    });

    it('should handle Windows paths', async () => {
      const folder = 'C:\\Music\\Collection';
      mockPost.mockResolvedValueOnce({ message: 'Added', settings: mockSettings });

      await settingsService.addScanFolder(folder);

      const callArg = mockPost.mock.calls[0][1];
      expect(callArg.folder).toBe(folder);
    });

    it('should propagate errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Folder already exists'));

      await expect(settingsService.addScanFolder('/music')).rejects.toThrow('Folder already exists');
    });
  });

  describe('removeScanFolder', () => {
    it('should remove scan folder successfully', async () => {
      const folder = '/music';
      const expectedResponse = {
        message: 'Scan folder removed',
        settings: { ...mockSettings, scan_folders: [] },
      };
      mockPost.mockResolvedValueOnce(expectedResponse);

      const result = await settingsService.removeScanFolder(folder);

      // Service uses POST to /scan-folders/delete endpoint
      expect(mockPost).toHaveBeenCalledWith('/api/settings/scan-folders/delete', { folder });
      expect(result).toEqual(expectedResponse);
    });

    it('should handle path with special characters', async () => {
      const folder = '/music/[Jazz] Collection';
      mockPost.mockResolvedValueOnce({ message: 'Removed', settings: mockSettings });

      await settingsService.removeScanFolder(folder);

      const callArg = mockPost.mock.calls[0][1];
      expect(callArg.folder).toBe(folder);
    });

    it('should propagate errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Folder not found'));

      await expect(settingsService.removeScanFolder('/nonexistent')).rejects.toThrow('Folder not found');
    });
  });
});
