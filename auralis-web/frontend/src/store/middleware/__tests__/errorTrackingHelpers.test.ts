/**
 * errorTrackingHelpers (#6702): the pure steps createErrorTrackingMiddleware composes.
 */

import { describe, it, expect, vi } from 'vitest';
import {
  buildTrackedError,
  detectActionError,
  notifyOnError,
  readActionShape,
} from '@/store/middleware/errorTrackingHelpers';
import { ErrorCategory } from '@/store/middleware/errorCategorization';

describe('readActionShape', () => {
  it('reads a string type and any payload', () => {
    expect(readActionShape({ type: 'player/setError', payload: 'boom' })).toEqual({
      type: 'player/setError',
      payload: 'boom',
    });
  });

  it('tolerates non-objects and a non-string type', () => {
    expect(readActionShape(null)).toEqual({ type: undefined, payload: undefined });
    expect(readActionShape({ type: 7 })).toEqual({ type: undefined, payload: undefined });
  });
});

describe('detectActionError', () => {
  it('takes the message from an object payload error field', () => {
    expect(detectActionError({ type: 'cache/load', payload: { error: 'disk full' } })).toEqual({
      message: 'disk full',
      context: { error: 'disk full' },
    });
  });

  it('falls back to the action type for an Error-typed object payload without a message', () => {
    expect(detectActionError({ type: 'queue/fetchFailure', payload: { id: 3 } })?.message).toBe(
      'queue/fetchFailure'
    );
  });

  it('tracks a string payload only for error-shaped types', () => {
    expect(detectActionError({ type: 'player/setError', payload: 'decode failed' })).toEqual({
      message: 'decode failed',
      context: { message: 'decode failed' },
    });
    expect(detectActionError({ type: 'player/setTitle', payload: 'Song' })).toBeNull();
  });

  it('ignores an ordinary object payload', () => {
    expect(detectActionError({ type: 'player/setVolume', payload: { volume: 0.5 } })).toBeNull();
  });
});

describe('buildTrackedError', () => {
  it('categorizes the message and defaults the action name', () => {
    const tracked = buildTrackedError('network timeout', undefined, { context: { a: 1 } });
    expect(tracked.category).toBe(ErrorCategory.NETWORK);
    expect(tracked.action).toBe('unknown');
    expect(tracked.context).toEqual({ a: 1 });
    expect(tracked.retryCount).toBe(0);
  });
});

describe('notifyOnError', () => {
  it('swallows a throwing callback and logs it when logging is on', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onError = vi.fn(() => {
      throw new Error('callback bug');
    });
    const tracked = buildTrackedError('x', 'a/b');

    expect(() => notifyOnError({ onError, logToConsole: true }, tracked)).not.toThrow();
    expect(onError).toHaveBeenCalledWith(tracked);
    expect(log).toHaveBeenCalledWith('[Error Tracking] onError callback threw:', expect.any(Error));
    log.mockRestore();
  });
});
