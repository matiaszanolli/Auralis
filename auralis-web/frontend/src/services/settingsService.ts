/**
 * Settings Service (Phase 5a)
 * ~~~~~~~~~~~~~~~~
 *
 * API service for user settings management.
 *
 * Refactored using Service Factory Pattern (Phase 5a) to reduce code duplication.
 */

import { ENDPOINTS } from '../config/api';
import { post } from '../utils/apiRequest';
import { createCrudService } from '../utils/serviceFactory';

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

// Create base CRUD service using factory
const crudService = createCrudService<UserSettings, SettingsUpdate>({
  list: ENDPOINTS.SETTINGS,
  update: ENDPOINTS.SETTINGS,
  custom: {
    reset: `${ENDPOINTS.SETTINGS}/reset`,
    addScanFolder: `${ENDPOINTS.SETTINGS}/scan-folders`,
    removeScanFolder: `${ENDPOINTS.SETTINGS}/scan-folders/delete`,
  },
});

/**
 * Get current user settings
 */
export async function getSettings(): Promise<UserSettings> {
  const result: any = await crudService.list();
  // Backend returns a single object; fall back to array handling for compat
  if (Array.isArray(result)) {
    if (result.length > 0) return result[0];
    throw new Error('No settings found');
  }
  return result as UserSettings;
}

/**
 * Update user settings
 */
export async function updateSettings(updates: SettingsUpdate): Promise<{ message: string; settings: UserSettings }> {
  return crudService.update(0, updates) as Promise<any>;
}

/**
 * Reset all settings to defaults
 */
export async function resetSettings(): Promise<{ message: string; settings: UserSettings }> {
  return crudService.custom('reset', 'post', {});
}

/**
 * Add a scan folder
 */
export async function addScanFolder(folder: string): Promise<{ message: string; settings: UserSettings }> {
  return crudService.custom('addScanFolder', 'post', { folder });
}

/**
 * Remove a scan folder
 */
export async function removeScanFolder(folder: string): Promise<{ message: string; settings: UserSettings }> {
  return crudService.custom('removeScanFolder', 'post', { folder });
}

/**
 * Trigger an immediate library scan on the given directories
 */
export async function triggerLibraryScan(directories: string[]): Promise<void> {
  await post(ENDPOINTS.LIBRARY_SCAN, { directories, recursive: true, skip_existing: true });
}

export const settingsService = {
  getSettings,
  updateSettings,
  resetSettings,
  addScanFolder,
  removeScanFolder,
  triggerLibraryScan,
};

export default settingsService;
