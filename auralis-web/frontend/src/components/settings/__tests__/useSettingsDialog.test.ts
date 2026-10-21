/**
 * useSettingsDialog cancelled-edit tests (#5618)
 *
 * The hook is mounted once for the app lifetime (ComfortableApp toggles the
 * dialog's `open`), so its state must not carry unsaved edits across a close:
 * Cancel/Esc/backdrop all land on `open: false`, and `getValue` prefers
 * `pendingChanges` — without the reset, a cancelled edit re-displayed as
 * stored and the next Save silently committed it.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSettingsDialog } from '../useSettingsDialog';
import { settingsService } from '@/services/settingsService';
import type { UserSettings } from '@/services/settingsService';

vi.mock('@/services/settingsService', () => ({
  settingsService: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    resetSettings: vi.fn(),
    addScanFolder: vi.fn(),
    removeScanFolder: vi.fn(),
    triggerLibraryScan: vi.fn(),
  },
}));

const mockSettings: UserSettings = {
  id: 1,
  scan_folders: ['/music'],
  file_types: ['flac'],
  auto_scan: true,
  scan_interval: 3600,
  crossfade_enabled: false,
  crossfade_duration: 0,
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
  auto_enhance: false,
  enhancement_intensity: null,
  cache_size: 1024,
  max_concurrent_scans: 4,
  enable_analytics: false,
  debug_mode: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('useSettingsDialog cancelled-edit reset (#5618)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
  });

  it('discards pending edits when the dialog closes, so a reopen shows stored values', async () => {
    const { result, rerender } = renderHook(
      ({ open }: { open: boolean }) => useSettingsDialog({ open }),
      { initialProps: { open: true } }
    );

    // Settings load and the edit lands.
    await act(async () => {});
    act(() => {
      result.current.handleSettingChange('cache_size', 512);
    });
    expect(result.current.getValue('cache_size')).toBe(512);

    // Cancel / Esc / backdrop — all just close the dialog.
    rerender({ open: false });
    rerender({ open: true });
    await act(async () => {});

    expect(result.current.getValue('cache_size')).toBe(1024);
    expect(result.current.pendingChanges).toEqual({});
  });

  it('clears transient error and remove-confirm state on close', async () => {
    const { result, rerender } = renderHook(
      ({ open }: { open: boolean }) => useSettingsDialog({ open }),
      { initialProps: { open: true } }
    );

    await act(async () => {});
    act(() => {
      result.current.handleSettingChange('volume', 0.5);
      result.current.handleRemoveScanFolder('/music');
    });
    expect(result.current.removeConfirmFolder).toBe('/music');

    rerender({ open: false });
    rerender({ open: true });
    await act(async () => {});

    expect(result.current.removeConfirmFolder).toBeNull();
  });

  it('still commits a normal edit on Save', async () => {
    vi.mocked(settingsService.updateSettings).mockResolvedValue({
      ...mockSettings,
      cache_size: 512,
    });
    const onClose = vi.fn();
    const { result } = renderHook(() => useSettingsDialog({ open: true }));

    await act(async () => {});
    act(() => {
      result.current.handleSettingChange('cache_size', 512);
    });
    await act(async () => {
      await result.current.handleSave(onClose);
    });

    expect(settingsService.updateSettings).toHaveBeenCalledWith({ cache_size: 512 });
    expect(result.current.pendingChanges).toEqual({});
    expect(onClose).toHaveBeenCalled();
  });
});
