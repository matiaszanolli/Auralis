/**
 * isLoading follows the LAST in-flight enhancement command (#6042)
 *
 * setPreset / setIntensity tolerate overlap (a newer call supersedes an older one), but every call
 * cleared the shared isLoading flag in its own `finally`, so a superseded call settling cleared it
 * while the newer POST was still in flight. setPreset's invalid-input path also left it set.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import * as WebSocketContextModule from '@/contexts/WebSocketContext';
import { useEnhancementControl } from '../useEnhancementControl';

vi.mock('@/hooks/api/useRestAPI');
vi.mock('@/hooks/websocket/useWebSocketMessages');

function deferred() {
  let resolve!: (value: unknown) => void;
  const promise = new Promise((res) => { resolve = res; });
  return { promise, resolve };
}

describe('useEnhancementCommands isLoading (#6042)', () => {
  beforeEach(() => {
    vi.spyOn(WebSocketContextModule, 'useWebSocketContext').mockReturnValue({
      reissueActiveStreamAs: vi.fn().mockReturnValue(false),
    } as never);
    vi.mocked(useWebSocketMessages).mockReturnValue(undefined as never);
  });

  it('stays loading until the newest overlapping command settles', async () => {
    const first = deferred();
    const second = deferred();
    const post = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    vi.mocked(useRestAPI).mockReturnValue({ get: vi.fn().mockResolvedValue(null), post } as never);
    const { result } = renderHook(() => useEnhancementControl());
    await act(async () => {});

    let a!: Promise<void>;
    let b!: Promise<void>;
    act(() => {
      a = result.current.setIntensity(0.4);
      b = result.current.setIntensity(0.6);
    });
    expect(result.current.isLoading).toBe(true);

    await act(async () => { first.resolve({}); await a; });
    expect(result.current.isLoading).toBe(true); // the newer POST is still in flight

    await act(async () => { second.resolve({}); await b; });
    expect(result.current.isLoading).toBe(false);
  });

  it('an invalid preset does not leave the hook stuck loading', async () => {
    vi.mocked(useRestAPI).mockReturnValue({ get: vi.fn().mockResolvedValue(null), post: vi.fn() } as never);
    const { result } = renderHook(() => useEnhancementControl());
    await act(async () => {});

    await act(async () => {
      await result.current.setPreset('not-a-preset' as never).catch(() => undefined);
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.error?.code).toBe('INVALID_PRESET');
  });
});
