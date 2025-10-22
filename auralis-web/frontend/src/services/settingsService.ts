/**
 * Settings Service
 * ~~~~~~~~~~~~~~~~
 *
 * API service for user settings management
 */

const API_BASE = 'http://localhost:8765/api';

export interface UserSettings {
  id: number;
  // Library
  scan_folders: string[];
  file_types: string[];
  auto_scan: boolean;
  scan_interval: number;
  // Playback
  crossfade_enabled: boolean;
  crossfade_duration: number;
  gapless_enabled: boolean;
  replay_gain_enabled: boolean;
  volume: number;
  // Audio
  output_device: string;
  bit_depth: number;
  sample_rate: number;
  // Interface
  theme: string;
  language: string;
  show_visualizations: boolean;
  mini_player_on_close: boolean;
  // Enhancement
  default_preset: string;
  auto_enhance: boolean;
  enhancement_intensity: number;
  // Advanced
  cache_size: number;
  max_concurrent_scans: number;
  enable_analytics: boolean;
  debug_mode: boolean;
  // Timestamps
  created_at: string;
  updated_at: string;
}

export interface SettingsUpdate {
  // Library
  scan_folders?: string[];
  file_types?: string[];
  auto_scan?: boolean;
  scan_interval?: number;
  // Playback
  crossfade_enabled?: boolean;
  crossfade_duration?: number;
  gapless_enabled?: boolean;
  replay_gain_enabled?: boolean;
  volume?: number;
  // Audio
  output_device?: string;
  bit_depth?: number;
  sample_rate?: number;
  // Interface
  theme?: string;
  language?: string;
  show_visualizations?: boolean;
  mini_player_on_close?: boolean;
  // Enhancement
  default_preset?: string;
  auto_enhance?: boolean;
  enhancement_intensity?: number;
  // Advanced
  cache_size?: number;
  max_concurrent_scans?: number;
  enable_analytics?: boolean;
  debug_mode?: boolean;
}

export const settingsService = {
  /**
   * Get current user settings
   */
  async getSettings(): Promise<UserSettings> {
    const response = await fetch(`${API_BASE}/settings`);
    if (!response.ok) {
      throw new Error('Failed to get settings');
    }
    return response.json();
  },

  /**
   * Update user settings
   */
  async updateSettings(updates: SettingsUpdate): Promise<{ message: string; settings: UserSettings }> {
    const response = await fetch(`${API_BASE}/settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updates)
    });

    if (!response.ok) {
      throw new Error('Failed to update settings');
    }

    return response.json();
  },

  /**
   * Reset all settings to defaults
   */
  async resetSettings(): Promise<{ message: string; settings: UserSettings }> {
    const response = await fetch(`${API_BASE}/settings/reset`, {
      method: 'POST'
    });

    if (!response.ok) {
      throw new Error('Failed to reset settings');
    }

    return response.json();
  },

  /**
   * Add a scan folder
   */
  async addScanFolder(folder: string): Promise<{ message: string; settings: UserSettings }> {
    const response = await fetch(`${API_BASE}/settings/scan-folders`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ folder })
    });

    if (!response.ok) {
      throw new Error('Failed to add scan folder');
    }

    return response.json();
  },

  /**
   * Remove a scan folder
   */
  async removeScanFolder(folder: string): Promise<{ message: string; settings: UserSettings }> {
    const response = await fetch(`${API_BASE}/settings/scan-folders`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ folder })
    });

    if (!response.ok) {
      throw new Error('Failed to remove scan folder');
    }

    return response.json();
  }
};

export default settingsService;
