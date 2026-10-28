/**
 * useShowVisualizations: the "Show visualizations" switch reaches the ambient background (#5676)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';

// A plain function behind the mock (not a vi.fn): a vi.fn that returns a rejected promise is
// reported by vitest as an unhandled error even when the caller handles it.
let nextSettings: () => Promise<unknown> = () => Promise.resolve({});
let settingsCalls = 0;
vi.mock('@/services/settingsService', () => ({
  SETTINGS_CHANGED_EVENT: 'auralis:settings-changed',
  getSettings: () => {
    settingsCalls += 1;
    return nextSettings();
  },
}));

import { useShowVisualizations } from '../useShowVisualizations';
import { SETTINGS_CHANGED_EVENT } from '@/services/settingsService';

const settings = (show: boolean) => ({ show_visualizations: show }) as never;

describe('useShowVisualizations', () => {
  beforeEach(() => {
    settingsCalls = 0;
    nextSettings = () => Promise.resolve({});
  });

  it('shows the background until the setting says otherwise', async () => {
    nextSettings = () => Promise.resolve(settings(true));

    const { result } = renderHook(() => useShowVisualizations());

    expect(result.current).toBe(true);
    await waitFor(() => expect(settingsCalls).toBeGreaterThan(0));
    expect(result.current).toBe(true);
  });

  it('hides it when the stored setting is off', async () => {
    nextSettings = () => Promise.resolve(settings(false));

    const { result } = renderHook(() => useShowVisualizations());

    await waitFor(() => expect(result.current).toBe(false));
  });

  it('follows a save made in the Settings dialog', async () => {
    nextSettings = () => Promise.resolve(settings(true));
    const { result } = renderHook(() => useShowVisualizations());
    await waitFor(() => expect(settingsCalls).toBeGreaterThan(0));

    act(() => {
      window.dispatchEvent(new CustomEvent(SETTINGS_CHANGED_EVENT, { detail: settings(false) }));
    });
    expect(result.current).toBe(false);

    act(() => {
      window.dispatchEvent(new CustomEvent(SETTINGS_CHANGED_EVENT, { detail: settings(true) }));
    });
    expect(result.current).toBe(true);
  });

  it('keeps showing it when the backend cannot be reached', async () => {
    nextSettings = () => Promise.reject(new Error('offline'));

    const { result } = renderHook(() => useShowVisualizations());

    await waitFor(() => expect(settingsCalls).toBeGreaterThan(0));
    expect(result.current).toBe(true);
  });

  it('stops listening on unmount', async () => {
    nextSettings = () => Promise.resolve(settings(true));
    const remove = vi.spyOn(window, 'removeEventListener');
    const { unmount } = renderHook(() => useShowVisualizations());

    unmount();

    expect(remove).toHaveBeenCalledWith(SETTINGS_CHANGED_EVENT, expect.any(Function));
  });
});
