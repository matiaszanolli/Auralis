/**
 * Keyboard seeks are coalesced (#5885).
 *
 * Holding an arrow key auto-repeats at ~30 Hz; each keydown used to commit a
 * seek (a stream restart), overrunning the backend's 10 msg/s limiter so the
 * final target could be rejected. A burst now commits the first press at once
 * and the final target once the keys go quiet.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { KeyboardEvent } from 'react';
import { KEY_SEEK_SETTLE_MS, useKeyboardSeek } from '../useKeyboardSeek';

function key(name: string): KeyboardEvent<HTMLDivElement> {
  return { key: name, preventDefault: vi.fn() } as unknown as KeyboardEvent<HTMLDivElement>;
}

function setup(currentTime = 90, duration = 200) {
  const onSeek = vi.fn();
  const { result } = renderHook(() => useKeyboardSeek({ currentTime, duration, onSeek, disabled: false }));
  return { result, onSeek };
}

describe('useKeyboardSeek (#5885)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('commits two seeks for 30 auto-repeated keydowns in one second, landing on the final target', () => {
    const { result, onSeek } = setup();
    for (let i = 0; i < 30; i++) {
      act(() => result.current.handleKeyDown(key('ArrowRight')));
      act(() => vi.advanceTimersByTime(33));
    }
    expect(onSeek).toHaveBeenCalledTimes(1);
    expect(onSeek).toHaveBeenLastCalledWith(91);
    // The preview follows the accumulated target, not the frozen clock.
    expect(result.current.keyboardTarget).toBe(120);

    act(() => vi.advanceTimersByTime(KEY_SEEK_SETTLE_MS));
    expect(onSeek).toHaveBeenCalledTimes(2);
    expect(onSeek).toHaveBeenLastCalledWith(120);
    expect(result.current.keyboardTarget).toBeNull();
  });

  it('a single press seeks immediately and commits nothing more', () => {
    const { result, onSeek } = setup();
    act(() => result.current.handleKeyDown(key('ArrowLeft')));
    expect(onSeek).toHaveBeenCalledWith(89);
    act(() => vi.advanceTimersByTime(KEY_SEEK_SETTLE_MS * 2));
    expect(onSeek).toHaveBeenCalledTimes(1);
  });

  it('clamps an accumulated burst to the track bounds', () => {
    const { result, onSeek } = setup(198, 200);
    for (let i = 0; i < 5; i++) act(() => result.current.handleKeyDown(key('ArrowRight')));
    act(() => vi.advanceTimersByTime(KEY_SEEK_SETTLE_MS));
    expect(onSeek).toHaveBeenLastCalledWith(200);
  });

  it('ignores unrelated keys without preventing their default', () => {
    const { result, onSeek } = setup();
    const event = key('a');
    act(() => result.current.handleKeyDown(event));
    expect(onSeek).not.toHaveBeenCalled();
    expect(event.preventDefault).not.toHaveBeenCalled();
  });
});
