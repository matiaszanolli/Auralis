import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { acceptSeq, isStaleSeq, useSyncWatermarks } from '../playerSyncWatermarks';

describe('acceptSeq / isStaleSeq', () => {
  it('accepts newer and equal seqs, advancing the watermark, and rejects strictly older ones', () => {
    const mark = { current: 5 };
    expect(acceptSeq(mark, 6)).toBe(true);
    expect(mark.current).toBe(6);
    expect(acceptSeq(mark, 6)).toBe(true); // a refinement of the current generation
    expect(acceptSeq(mark, 5)).toBe(false);
    expect(mark.current).toBe(6); // a rejected frame never moves the watermark
  });

  it('always accepts a frame with no numeric seq (an older backend) and leaves the mark alone', () => {
    const mark = { current: 9 };
    expect(acceptSeq(mark, undefined)).toBe(true);
    expect(acceptSeq(mark, '12')).toBe(true);
    expect(mark.current).toBe(9);
  });

  it('isStaleSeq only reads: strictly older is stale, equal is not, non-numbers are not', () => {
    const mark = { current: 4 };
    expect(isStaleSeq(mark, 3)).toBe(true);
    expect(isStaleSeq(mark, 4)).toBe(false);
    expect(isStaleSeq(mark, undefined)).toBe(false);
    expect(mark.current).toBe(4);
  });
});

describe('useSyncWatermarks', () => {
  it('keeps the four watermarks independent', () => {
    const { result } = renderHook(() => useSyncWatermarks());
    acceptSeq(result.current.state, 10);
    acceptSeq(result.current.volume, 2);

    expect(result.current.trackChanged.current).toBe(0);
    expect(result.current.transport.current).toBe(0);
    expect(acceptSeq(result.current.trackChanged, 1)).toBe(true); // not rejected by state's 10
  });

  it('resets every watermark when the backend restarts, but not on the first frame or a reconnect', () => {
    const { result } = renderHook(() => useSyncWatermarks());

    result.current.observeServerInstance('boot-1'); // first frame: nothing to reset
    acceptSeq(result.current.state, 50);
    acceptSeq(result.current.transport, 7);

    result.current.observeServerInstance('boot-1'); // same process (a reconnect)
    expect(result.current.state.current).toBe(50);

    result.current.observeServerInstance('boot-2'); // fresh process: counters restart
    expect([
      result.current.state.current,
      result.current.trackChanged.current,
      result.current.transport.current,
      result.current.volume.current,
    ]).toEqual([0, 0, 0, 0]);
    expect(acceptSeq(result.current.state, 1)).toBe(true);
  });

  it('ignores a frame without a server_instance_id', () => {
    const { result } = renderHook(() => useSyncWatermarks());
    result.current.observeServerInstance('boot-1');
    acceptSeq(result.current.state, 8);
    result.current.observeServerInstance(undefined);
    expect(result.current.state.current).toBe(8);
  });
});
