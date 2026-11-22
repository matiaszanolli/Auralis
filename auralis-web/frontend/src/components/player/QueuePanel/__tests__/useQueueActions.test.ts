/**
 * useQueueActions (#6703): control-bar actions and the Clear Queue confirmation.
 */

import { describe, it, expect, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useQueueActions } from '@/components/player/QueuePanel/useQueueActions';

function setup(overrides: Partial<Parameters<typeof useQueueActions>[0]> = {}) {
  const deps = {
    toggleShuffle: vi.fn(() => Promise.resolve()),
    setRepeatMode: vi.fn(() => Promise.resolve()),
    clearQueue: vi.fn(() => Promise.resolve()),
    ...overrides,
  };
  return { deps, hook: renderHook(() => useQueueActions(deps)) };
}

describe('useQueueActions', () => {
  it('clears the queue only after confirmation, and closes the dialog first', async () => {
    const { deps, hook } = setup();

    act(() => hook.result.current.requestClearQueue());
    expect(hook.result.current.showClearConfirm).toBe(true);
    expect(deps.clearQueue).not.toHaveBeenCalled();

    await act(() => hook.result.current.confirmClearQueue());
    expect(deps.clearQueue).toHaveBeenCalledTimes(1);
    expect(hook.result.current.showClearConfirm).toBe(false);
  });

  it('cancel closes the dialog without clearing', () => {
    const { deps, hook } = setup();
    act(() => hook.result.current.requestClearQueue());
    act(() => hook.result.current.cancelClearQueue());
    expect(hook.result.current.showClearConfirm).toBe(false);
    expect(deps.clearQueue).not.toHaveBeenCalled();
  });

  it('passes the repeat mode through and logs a failed action instead of throwing', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { deps, hook } = setup({ toggleShuffle: vi.fn(() => Promise.reject(new Error('offline'))) });

    await act(() => hook.result.current.handleSetRepeatMode('all'));
    expect(deps.setRepeatMode).toHaveBeenCalledWith('all');

    await expect(hook.result.current.handleToggleShuffle()).resolves.toBeUndefined();
    expect(log).toHaveBeenCalledWith('Failed to toggle shuffle:', expect.any(Error));
    log.mockRestore();
  });
});
