/**
 * useAutoHide (#5012)
 *
 * Extracted from ConnectionStatusIndicator (#4186) with no dedicated test of
 * its own — its sole caller's test never used fake timers, leaving the
 * timer-clear-on-deactivate/unmount behavior unguarded.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useAutoHide } from '../useAutoHide';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('useAutoHide (#5012)', () => {
  it('fires onHide after delayMs while active', () => {
    const onHide = vi.fn();
    renderHook(() => useAutoHide(true, onHide, 2000));

    expect(onHide).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1999);
    expect(onHide).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onHide).toHaveBeenCalledTimes(1);
  });

  it('does not fire while inactive', () => {
    const onHide = vi.fn();
    renderHook(() => useAutoHide(false, onHide, 2000));

    vi.advanceTimersByTime(5000);
    expect(onHide).not.toHaveBeenCalled();
  });

  it('cancels the pending timer when active becomes false before it elapses', () => {
    const onHide = vi.fn();
    const { rerender } = renderHook(
      ({ active }) => useAutoHide(active, onHide, 2000),
      { initialProps: { active: true } },
    );

    vi.advanceTimersByTime(1000);
    rerender({ active: false });
    vi.advanceTimersByTime(5000);

    expect(onHide).not.toHaveBeenCalled();
  });

  it('cancels the pending timer on unmount, so onHide never fires after unmount', () => {
    const onHide = vi.fn();
    const { unmount } = renderHook(() => useAutoHide(true, onHide, 2000));

    vi.advanceTimersByTime(1000);
    unmount();
    vi.advanceTimersByTime(5000);

    expect(onHide).not.toHaveBeenCalled();
  });

  it('always calls the latest onHide, without re-arming the timer for identity-only changes', () => {
    const firstOnHide = vi.fn();
    const secondOnHide = vi.fn();
    const { rerender } = renderHook(
      ({ onHide }) => useAutoHide(true, onHide, 2000),
      { initialProps: { onHide: firstOnHide } },
    );

    // New callback identity with the same active/delayMs — effect deps are
    // unchanged, so the original timer (armed at t=0) keeps running.
    vi.advanceTimersByTime(1000);
    rerender({ onHide: secondOnHide });
    vi.advanceTimersByTime(1000);

    expect(firstOnHide).not.toHaveBeenCalled();
    expect(secondOnHide).toHaveBeenCalledTimes(1);
  });

  it('respects a custom delayMs', () => {
    const onHide = vi.fn();
    renderHook(() => useAutoHide(true, onHide, 500));

    vi.advanceTimersByTime(499);
    expect(onHide).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onHide).toHaveBeenCalledTimes(1);
  });
});
