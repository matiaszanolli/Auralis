/**
 * Enhancement broadcast re-issue (#5864)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 * The Settings dialog's Auto-enhance save re-seeds the backend's runtime
 * `enabled` flag and broadcasts `enhancement_settings_changed`; the running
 * stream loop re-reads the flag per chunk, stops early, and nothing re-issued
 * — playback went silent after the buffer played out while the UI stayed
 * 'streaming'. The broadcast handler now re-issues as play_normal/play_enhanced
 * for changes that did not originate from this client's own commands.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  isExternalChange,
  markLocalEnhancementCommand,
  oncePerMessage,
} from '../enhancementBroadcastReissue';

describe('enhancementBroadcastReissue guards (#5864)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it('a fresh boot treats a change as external', () => {
    vi.setSystemTime(10_000_000);
    expect(isExternalChange()).toBe(true);
  });

  it('a local command suppresses the following broadcast within the window', () => {
    vi.setSystemTime(10_000_000);
    markLocalEnhancementCommand();
    vi.advanceTimersByTime(500);
    expect(isExternalChange()).toBe(false);

    vi.advanceTimersByTime(2_000);
    expect(isExternalChange()).toBe(true);
  });

  it('runs the re-issue exactly once per broadcast message across subscribers', () => {
    const message = { type: 'enhancement_settings_changed', data: { enabled: false } };
    const first = vi.fn();
    const second = vi.fn();

    oncePerMessage(message, first);
    oncePerMessage(message, second);

    expect(first).toHaveBeenCalledTimes(1);
    expect(second).not.toHaveBeenCalled();
  });

  it('different messages each get their own single run', () => {
    oncePerMessage({ data: {} }, () => {});
    const fn = vi.fn();
    oncePerMessage({ data: {} }, fn);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
