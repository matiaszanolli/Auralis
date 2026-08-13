/**
 * `errorActions` narrows error detection, and by default does nothing (#4662)
 *
 * `ErrorTrackingConfig.errorActions` read like a scoping allowlist and shipped a
 * default of `['setError', 'setLastError']`, but the middleware body never
 * referenced it — the field had a declaration and a default and no read at all.
 * Anyone passing a custom list to constrain the substring heuristic got no
 * effect and no warning.
 *
 * ## Why the shipped default is gone rather than enforced
 *
 * Wiring the field while keeping `['setError', 'setLastError']` would have been
 * a silent regression, not a fix. Real slice actions include
 * `player/setStreamingError` and `connection/setConnectionError`, and neither
 * matches those two entries — so the middleware would have stopped tracking
 * errors it tracks today. Since the default was never read it carried no
 * behaviour to preserve, so `errorActions` is now simply absent by default,
 * meaning "unrestricted", and the knob is a genuine opt-in narrowing.
 *
 * That is the issue's RETURN VALUE check: an allowlist makes non-matching
 * actions return early, and this verifies it does not suppress errors the app
 * relies on.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer, {
  setError as playerSetError,
  setStreamingError,
  setVolume,
} from '@/store/slices/playerSlice';
import connectionReducer from '@/store/slices/connectionSlice';
import {
  createErrorTrackingMiddleware,
  isAllowedErrorAction,
  type ErrorTrackingConfig,
  type TrackedError,
} from '../errorTrackingMiddleware';

function makeStore(config: ErrorTrackingConfig) {
  return configureStore({
    reducer: { player: playerReducer, connection: connectionReducer },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware().concat(createErrorTrackingMiddleware(config)),
  });
}

describe('isAllowedErrorAction (#4662)', () => {
  it('permits everything when no list is configured', () => {
    expect(isAllowedErrorAction('player/setError', undefined)).toBe(true);
    expect(isAllowedErrorAction('anything/at/all', undefined)).toBe(true);
  });

  it('treats an empty list as unrestricted, not as "deny all"', () => {
    // A caller building the list dynamically can legitimately end up with [];
    // reading that as "block every error" would be a trap.
    expect(isAllowedErrorAction('player/setError', [])).toBe(true);
  });

  it('matches the action name after the last slash', () => {
    expect(isAllowedErrorAction('player/setError', ['setError'])).toBe(true);
    expect(isAllowedErrorAction('library/setError', ['setError'])).toBe(true);
  });

  it('matches a fully-qualified action type', () => {
    expect(isAllowedErrorAction('player/setError', ['player/setError'])).toBe(true);
    expect(isAllowedErrorAction('library/setError', ['player/setError'])).toBe(false);
  });

  it('does not match on substrings', () => {
    // 'player/setStreamingError' must not slip through a 'setError' entry —
    // that looseness is what made the original heuristic over-broad.
    expect(isAllowedErrorAction('player/setStreamingError', ['setError'])).toBe(false);
  });

  it('rejects an undefined action type when a list is configured', () => {
    expect(isAllowedErrorAction(undefined, ['setError'])).toBe(false);
  });
});

describe('errorActions narrows detection when configured (#4662)', () => {
  let onError: ReturnType<typeof vi.fn<(error: TrackedError) => void>>;

  beforeEach(() => {
    onError = vi.fn();
  });

  it('tracks an action on the allowlist', () => {
    const store = makeStore({ enabled: true, onError, errorActions: ['setError'] });

    store.dispatch(playerSetError('Playback failed'));

    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('does NOT track an error action absent from the allowlist', () => {
    const store = makeStore({ enabled: true, onError, errorActions: ['setCustomError'] });

    store.dispatch(playerSetError('Playback failed'));

    expect(onError).not.toHaveBeenCalled();
  });

  it('the allowlist narrows only — it cannot make a non-error action tracked', () => {
    // Listing an action that the heuristic never flags must not start tracking
    // it; the allowlist is an AND, not an OR.
    const store = makeStore({ enabled: true, onError, errorActions: ['setVolume'] });

    store.dispatch(setVolume(50));

    expect(onError).not.toHaveBeenCalled();
  });
});

describe('the default config is unrestricted (#4662)', () => {
  let onError: ReturnType<typeof vi.fn<(error: TrackedError) => void>>;

  beforeEach(() => {
    onError = vi.fn();
  });

  it('tracks setError with no errorActions configured', () => {
    const store = makeStore({ enabled: true, onError });

    store.dispatch(playerSetError('Playback failed'));

    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('still tracks setStreamingError — the regression the old default would have caused', () => {
    // This is the discriminating test. Enforcing the shipped
    // ['setError', 'setLastError'] default would have dropped this action,
    // because 'setStreamingError' matches neither entry.
    const store = makeStore({ enabled: true, onError });

    store.dispatch(setStreamingError({ streamType: 'enhanced', error: 'Stream died' }));

    expect(onError).toHaveBeenCalled();
    const tracked = onError.mock.calls[0][0] as TrackedError;
    expect(tracked.action).toContain('setStreamingError');
  });

  it('the old default would have excluded it — proving the test above discriminates', () => {
    expect(isAllowedErrorAction('player/setStreamingError', ['setError', 'setLastError']))
      .toBe(false);
  });

  it('still ignores success actions', () => {
    const store = makeStore({ enabled: true, onError });

    store.dispatch(setVolume(50));

    expect(onError).not.toHaveBeenCalled();
  });
});
