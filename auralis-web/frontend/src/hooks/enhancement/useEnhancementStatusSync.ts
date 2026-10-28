/**
 * useEnhancementStatusSync - keeps an EnhancementState in step with the server.
 *
 * Split out of useEnhancementControl.ts (#5840): the initial status GET (with
 * its module-level in-flight dedup) and the `enhancement_settings_changed`
 * WebSocket subscription.
 *
 * @module hooks/enhancement/useEnhancementStatusSync
 */

import { useEffect, useRef, type Dispatch, type SetStateAction } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import { isExternalChange, oncePerMessage } from './enhancementBroadcastReissue';
import type { EnhancementState } from './enhancementState';

// Module-level in-flight dedup so multiple consumers mounting at once
// (EnhancementPane, Expanded, AlbumCharacterPane, ...) share a single GET to
// /api/player/enhancement/status instead of each firing their own (#3955).
// Only the in-flight promise is shared — it is cleared once settled, so a later
// mount re-fetches fresh state. The WS `enhancement_settings_changed` broadcast
// keeps every mounted consumer in sync after the initial load.
//
// The wire payload is EnhancementState minus lastUpdated — that field is set
// client-side by every consumer, so typing the fetch as the full state used to
// promise a `lastUpdated` the server never sends (#5637).
let _sharedStatusPromise: Promise<Omit<EnhancementState, 'lastUpdated'> | null> | null = null;

function _fetchEnhancementStatusOnce(
  getter: <T>(url: string) => Promise<T | null>,
): Promise<Omit<EnhancementState, 'lastUpdated'> | null> {
  if (_sharedStatusPromise) {
    return _sharedStatusPromise;
  }
  const promise = getter<Omit<EnhancementState, 'lastUpdated'>>('/api/player/enhancement/status')
    .finally(() => {
      // Clear once settled so the next (non-concurrent) mount fetches fresh.
      if (_sharedStatusPromise === promise) _sharedStatusPromise = null;
    });
  _sharedStatusPromise = promise;
  return promise;
}

/** The broadcast's settings, as `onExternalChange` receives them. */
export type EnhancementSettingsChange = Partial<Pick<EnhancementState, 'enabled' | 'preset' | 'intensity'>>;

/**
 * `onExternalChange`: invoked with the broadcast's settings when the change
 * did NOT originate from this client's own REST commands (Settings saves,
 * another client). Both kinds of change need the active stream re-issued:
 * the loop stops when `enabled` flips false (#5864), and preset/intensity
 * are bound when the stream starts, so without a re-issue the running stream
 * and every later seek keep the old values (#5874).
 */
export function useEnhancementStatusSync(
  setState: Dispatch<SetStateAction<EnhancementState>>,
  onExternalChange?: (change: EnhancementSettingsChange) => void,
): void {
  const { get } = useRestAPI();
  const getRef = useRef(get);
  getRef.current = get;

  /**
   * Subscribe to real-time enhancement setting changes via WebSocket
   */
  useWebSocketMessages(
    ['enhancement_settings_changed'],
    (message) => {
      const enhancementMsg = message; // narrowed to EnhancementSettingsChangedMessage (#5636)

      // An externally-originated change (Settings save) must re-issue the
      // active stream (#5864, #5874). Local commands re-issue on their own,
      // so their confirmation broadcast is suppressed; several mounted
      // subscribers share one message instance, so the guard is once-per-
      // message. Runs BEFORE setState so the callback compares against the
      // prior state through its own refs.
      if (onExternalChange && isExternalChange()) {
        const { enabled, preset, intensity } = enhancementMsg.data;
        oncePerMessage(message, () => onExternalChange({ enabled, preset, intensity }));
      }

      setState((prevState) => ({
        ...prevState,
        enabled: enhancementMsg.data.enabled ?? prevState.enabled,
        preset: enhancementMsg.data.preset ?? prevState.preset,
        intensity: enhancementMsg.data.intensity ?? prevState.intensity,
        lastUpdated: Date.now(),
      }));
    }
  );

  /**
   * Fetch initial enhancement state on mount
   */
  useEffect(() => {
    let cancelled = false;
    const fetchInitialState = async () => {
      try {
        // Shared module-level fetch — concurrent consumers dedupe to one GET (#3955).
        const response = await _fetchEnhancementStatusOnce(getRef.current);

        if (response && !cancelled) {
          setState({
            enabled: response.enabled,
            preset: response.preset,
            intensity: response.intensity,
            lastUpdated: Date.now(),
          });
        }
      } catch (err) {
        // Silently fail - user can still interact with defaults
        console.warn('Failed to fetch initial enhancement state:', err);
      }
    };

    fetchInitialState();
    return () => { cancelled = true; };
  }, []);
}
