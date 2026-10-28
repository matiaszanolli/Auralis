/**
 * The shared initial-status GET survives its first consumer unmounting (#5655)
 *
 * Concurrent consumers dedupe to one GET built with the FIRST consumer's `useRestAPI().get`. When
 * that consumer unmounts mid-flight its hook aborts the request, and every other consumer waiting
 * on the shared promise got the AbortError, swallowed it and stayed on the disabled defaults. A
 * consumer that is still mounted now asks again.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import { useEnhancementStatusSync } from '../useEnhancementStatusSync';
import { INITIAL_STATE, type EnhancementState } from '../enhancementState';

vi.mock('@/hooks/api/useRestAPI');
vi.mock('@/hooks/websocket/useWebSocketMessages');

const SERVER = { enabled: true, preset: 'adaptive', intensity: 0.7 };

function useConsumer() {
  const [state, setState] = useState<EnhancementState>(INITIAL_STATE);
  useEnhancementStatusSync(setState);
  return state;
}

function abortError(): Error {
  const error = new Error('The operation was aborted');
  error.name = 'AbortError';
  return error;
}

describe('useEnhancementStatusSync shared fetch (#5655)', () => {
  beforeEach(() => {
    vi.mocked(useWebSocketMessages).mockReturnValue(undefined as never);
  });

  it('a surviving consumer retries after the initiating consumer aborted the shared GET', async () => {
    let rejectFirst: (error: Error) => void = () => {};
    const firstGet = vi.fn(() => new Promise((_resolve, reject) => { rejectFirst = reject; }));
    const secondGet = vi.fn().mockResolvedValue(SERVER);

    vi.mocked(useRestAPI).mockReturnValueOnce({ get: firstGet } as never);
    const first = renderHook(() => useConsumer());
    vi.mocked(useRestAPI).mockReturnValue({ get: secondGet } as never);
    const second = renderHook(() => useConsumer());

    // The first consumer unmounts mid-flight and its hook aborts the shared request.
    first.unmount();
    await act(async () => { rejectFirst(abortError()); });

    await waitFor(() => expect(second.result.current.enabled).toBe(true));
    expect(second.result.current.intensity).toBe(0.7);
    expect(secondGet).toHaveBeenCalledTimes(1);
  });

  it('a failure that is not an abort is still logged and leaves the defaults', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.mocked(useRestAPI).mockReturnValue({ get: vi.fn().mockRejectedValue(new Error('500')) } as never);

    const { result } = renderHook(() => useConsumer());

    await waitFor(() => expect(warn).toHaveBeenCalled());
    expect(result.current.enabled).toBe(INITIAL_STATE.enabled);
  });

  it('an unmounted consumer does not retry on its own abort', async () => {
    const get = vi.fn(() => Promise.reject(abortError()));
    vi.mocked(useRestAPI).mockReturnValue({ get } as never);

    const { unmount } = renderHook(() => useConsumer());
    unmount();
    await act(async () => {});

    expect(get).toHaveBeenCalledTimes(1);
  });
});
