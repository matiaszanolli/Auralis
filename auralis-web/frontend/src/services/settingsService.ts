/**
 * Settings Service
 * ~~~~~~~~~~~~~~~~
 *
 * API service for user settings management
 */

import { get, put, post } from '../utils/apiRequest';
import { ENDPOINTS } from '../config/api';

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
    return get(ENDPOINTS.SETTINGS);
  },

  /**
   * Update user settings
   */
  async updateSettings(updates: SettingsUpdate): Promise<{ message: string; settings: UserSettings }> {
    return put(ENDPOINTS.SETTINGS, updates);
  },

  /**
   * Reset all settings to defaults
   */
  async resetSettings(): Promise<{ message: string; settings: UserSettings }> {
    return post(`${ENDPOINTS.SETTINGS}/reset`, {});
  },

  /**
   * Add a scan folder
   */
  async addScanFolder(folder: string): Promise<{ message: string; settings: UserSettings }> {
    return post(`${ENDPOINTS.SETTINGS}/scan-folders`, { folder });
  },

  /**
   * Remove a scan folder
   */
  async removeScanFolder(folder: string): Promise<{ message: string; settings: UserSettings }> {
    return post(`${ENDPOINTS.SETTINGS}/scan-folders/delete`, { folder });
  }
};

export default settingsService;
