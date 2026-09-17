/**
 * useServerRestartNotice (#5487): a backend restart drops the in-memory
 * playback session; the client must say so instead of silently showing an
 * empty player.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

let deliver: ((message: unknown) => void) | undefined;

vi.mock('@/hooks/websocket/useWebSocketMessages', () => ({
  useWebSocketMessages: vi.fn((_types: string[], callback: (msg: unknown) => void) => {
    deliver = callback;
  }),
}));

const mockWarning = vi.fn();

vi.mock('@/components/shared/Toast', () => ({
  useToast: vi.fn(() => ({ warning: mockWarning })),
}));

import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import { SESSION_RESET_MESSAGE, useServerRestartNotice } from '../useServerRestartNotice';

const TRACK = { id: 1, title: 'T', artist: 'A', album: 'B', duration: 10 };

function snapshot(instanceId: string | undefined, loaded: 'track' | 'queue' | 'none') {
  return {
    type: 'player_state',
    data: {
      server_instance_id: instanceId,
      current_track: loaded === 'track' ? TRACK : null,
      queue: loaded === 'queue' ? [TRACK] : [],
    },
  };
}

describe('useServerRestartNotice', () => {
  beforeEach(() => {
    deliver = undefined;
    mockWarning.mockClear();
    renderHook(() => useServerRestartNotice());
  });

  it('subscribes to player_state', () => {
    expect(useWebSocketMessages).toHaveBeenCalledWith(['player_state'], expect.any(Function));
  });

  it('warns when the instance changes after a track was loaded', () => {
    deliver!(snapshot('boot-1', 'track'));
    deliver!(snapshot('boot-2', 'none'));

    expect(mockWarning).toHaveBeenCalledTimes(1);
    expect(mockWarning).toHaveBeenCalledWith(SESSION_RESET_MESSAGE, expect.any(Number));
  });

  it('warns when only a queue was loaded', () => {
    deliver!(snapshot('boot-1', 'queue'));
    deliver!(snapshot('boot-2', 'none'));

    expect(mockWarning).toHaveBeenCalledTimes(1);
  });

  it('stays quiet on the first snapshot and within one backend process', () => {
    deliver!(snapshot('boot-1', 'track'));
    deliver!(snapshot('boot-1', 'none'));
    deliver!(snapshot('boot-1', 'track'));

    expect(mockWarning).not.toHaveBeenCalled();
  });

  it('stays quiet when nothing was loaded before the restart', () => {
    deliver!(snapshot('boot-1', 'none'));
    deliver!(snapshot('boot-2', 'none'));

    expect(mockWarning).not.toHaveBeenCalled();
  });

  it('warns once per restart, not on every later snapshot', () => {
    deliver!(snapshot('boot-1', 'track'));
    deliver!(snapshot('boot-2', 'none'));
    deliver!(snapshot('boot-2', 'none'));

    expect(mockWarning).toHaveBeenCalledTimes(1);
  });

  it('ignores snapshots without an instance id', () => {
    deliver!(snapshot('boot-1', 'track'));
    deliver!(snapshot(undefined, 'none'));
    deliver!(snapshot('boot-1', 'none'));

    expect(mockWarning).not.toHaveBeenCalled();
  });
});
