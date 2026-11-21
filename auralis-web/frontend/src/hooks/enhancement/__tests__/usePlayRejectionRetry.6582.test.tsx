/**
 * A play_* the WebSocket limiter rejects is retried once, not silently lost (#6582).
 *
 * After a skip burst the backend answers some play_enhanced frames with `error{command}` and
 * nothing else; the UI then named the last requested track while an earlier one played.
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { Provider } from 'react-redux';
import { createTestStore } from '@/test/test-utils';
import { resetStreaming, startStreaming } from '@/store/slices/playerSlice';
import { usePlayRejectionRetry } from '../usePlayRejectionRetry';
import { SEEK_RETRY_DELAY_MS } from '../useEnhancedSeek';
import type { CurrentTrackInfo } from '../useEnhancedStreamStart';

type ErrorHandler = (message: { type: 'error'; error: string; message: string; command?: string | null }) => void;

function setup() {
  const store = createTestStore();
  let onError: ErrorHandler | undefined;
  const subscribe = vi.fn((type: string, handler: ErrorHandler) => {
    if (type === 'error') onError = handler;
    return vi.fn();
  });
  const currentTrackInfoRef: { current: CurrentTrackInfo | null } = { current: null };
  // Stands in for useEnhancedPlayCommand: records the track and enters buffering.
  const sendPlay = vi.fn(async (trackId: number) => {
    currentTrackInfoRef.current = { trackId };
    store.dispatch(startStreaming({ streamType: 'enhanced', trackId, totalChunks: 0 }));
  });
  const wrapper = ({ children }: { children: React.ReactNode }) => <Provider store={store}>{children}</Provider>;
  const { result } = renderHook(
    () => usePlayRejectionRetry(subscribe as never, store.dispatch, sendPlay, currentTrackInfoRef),
    { wrapper }
  );
  const reject = (error: string, command: string | null = 'play_enhanced') =>
    act(() => onError?.({ type: 'error', error, message: error, command }));
  const enhanced = () => store.getState().player.streaming.enhanced;
  return { store, result, sendPlay, reject, enhanced };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('usePlayRejectionRetry (#6582)', () => {
  it('re-sends a rate-limited play once after the limiter window, then gives up with an error', async () => {
    const { result, sendPlay, reject, enhanced } = setup();
    await act(() => result.current(7, 'adaptive', 1, 'enhanced'));

    reject('rate_limit_exceeded');
    expect(sendPlay).toHaveBeenCalledTimes(1);
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS));
    expect(sendPlay).toHaveBeenCalledTimes(2);
    expect(sendPlay).toHaveBeenLastCalledWith(7, 'adaptive', 1, 'enhanced');

    // A second rejection of the retry does not loop: it surfaces instead of buffering forever.
    reject('rate_limit_exceeded');
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS * 3));
    expect(sendPlay).toHaveBeenCalledTimes(2);
    expect(enhanced().state).toBe('error');
  });

  it('matches the rejection to the wire command of the pending play', async () => {
    const { result, sendPlay, reject, enhanced } = setup();
    await act(() => result.current(7, 'adaptive', 1, 'normal'));

    reject('rate_limit_exceeded', 'play_enhanced');
    reject('rate_limit_exceeded', 'seek');
    reject('rate_limit_exceeded', null);
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS * 2));
    expect(sendPlay).toHaveBeenCalledTimes(1);
    expect(enhanced().state).toBe('buffering');

    reject('rate_limit_exceeded', 'play_normal');
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS));
    expect(sendPlay).toHaveBeenCalledTimes(2);
  });

  it('does not retry after the user stopped in the meantime', async () => {
    const { store, result, sendPlay, reject } = setup();
    await act(() => result.current(7, 'adaptive', 1, 'enhanced'));

    reject('rate_limit_exceeded');
    act(() => { store.dispatch(resetStreaming('enhanced')); });
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS));
    expect(sendPlay).toHaveBeenCalledTimes(1);
  });

  it('a newer play supersedes the scheduled retry of an older one', async () => {
    const { result, sendPlay, reject } = setup();
    await act(() => result.current(7, 'adaptive', 1, 'enhanced'));
    reject('rate_limit_exceeded');
    await act(() => result.current(8, 'adaptive', 1, 'enhanced'));

    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS * 2));
    expect(sendPlay.mock.calls.map((call) => call[0])).toEqual([7, 8]);
  });

  it('surfaces a non-rate-limit rejection as a streaming error without retrying', async () => {
    const { result, sendPlay, reject, enhanced } = setup();
    await act(() => result.current(7, 'adaptive', 1, 'enhanced'));

    reject('invalid_force');
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS * 2));
    expect(sendPlay).toHaveBeenCalledTimes(1);
    expect(enhanced().state).toBe('error');
    expect(enhanced().error).toContain('invalid_force');
  });
});
