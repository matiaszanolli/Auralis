/**
 * The initial status GET never overwrites a newer write (#5655)
 *
 * The GET reports the server as of when it was asked. If a WS `enhancement_settings_changed` frame
 * (or a local command) lands while it is in flight, applying the GET afterwards rolled the UI back
 * to the older value.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import { useEnhancementStatusSync } from '../useEnhancementStatusSync';
import { INITIAL_STATE, type EnhancementState } from '../enhancementState';

vi.mock('@/hooks/api/useRestAPI');
vi.mock('@/hooks/websocket/useWebSocketMessages');

function useConsumer() {
  const [state, setState] = useState<EnhancementState>({ ...INITIAL_STATE, lastUpdated: 0 });
  useEnhancementStatusSync(setState);
  return { state, setState };
}

describe('useEnhancementStatusSync: GET vs newer writes (#5655)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(10_000);
  });
  afterEach(() => vi.useRealTimers());

  function deferredGet() {
    let resolve: (value: unknown) => void = () => {};
    const get = vi.fn(() => new Promise((res) => { resolve = res; }));
    vi.mocked(useRestAPI).mockReturnValue({ get } as never);
    return { get, answer: (value: unknown) => resolve(value) };
  }

  it('applies the GET when nothing else wrote while it was in flight', async () => {
    const { answer } = deferredGet();
    vi.mocked(useWebSocketMessages).mockReturnValue(undefined as never);

    const { result } = renderHook(() => useConsumer());
    await act(async () => { answer({ enabled: true, preset: 'adaptive', intensity: 0.7 }); });

    await waitFor(() => expect(result.current.state.enabled).toBe(true));
    expect(result.current.state.intensity).toBe(0.7);
  });

  it('keeps a WS broadcast that arrived before the GET answered', async () => {
    const { answer } = deferredGet();
    let onBroadcast: (message: unknown) => void = () => {};
    vi.mocked(useWebSocketMessages).mockImplementation(((_types: unknown, handler: (m: unknown) => void) => {
      onBroadcast = handler;
    }) as never);

    const { result } = renderHook(() => useConsumer());
    vi.setSystemTime(10_005);
    act(() => { onBroadcast({ type: 'enhancement_settings_changed', data: { enabled: false, preset: 'adaptive', intensity: 0.2 } }); });
    await act(async () => { answer({ enabled: true, preset: 'adaptive', intensity: 0.9 }); }); // older server snapshot

    expect(result.current.state.enabled).toBe(false);
    expect(result.current.state.intensity).toBe(0.2);
  });

  it('keeps a local command applied while the GET was in flight', async () => {
    const { answer } = deferredGet();
    vi.mocked(useWebSocketMessages).mockReturnValue(undefined as never);

    const { result } = renderHook(() => useConsumer());
    vi.setSystemTime(10_005);
    act(() => { result.current.setState((prev) => ({ ...prev, intensity: 0.3, lastUpdated: Date.now() })); });
    await act(async () => { answer({ enabled: true, preset: 'adaptive', intensity: 0.9 }); });

    expect(result.current.state.intensity).toBe(0.3);
  });
});
