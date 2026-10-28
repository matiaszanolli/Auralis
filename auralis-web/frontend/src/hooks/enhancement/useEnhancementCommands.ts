/**
 * useEnhancementCommands - the toggle / preset / intensity commands.
 *
 * Split out of useEnhancementControl.ts (#5840): each command POSTs the change,
 * applies it optimistically, and re-issues the active stream so the change
 * reaches the audio path (the backend binds preset/intensity at
 * ChunkedAudioProcessor construction). The control hook owns the state and the
 * latest-value refs; this hook owns the in-flight guards.
 *
 * @module hooks/enhancement/useEnhancementCommands
 */

import { useCallback, useRef, type Dispatch, type MutableRefObject, type SetStateAction } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import type { ApiError } from '@/types/api';
import { markLocalEnhancementCommand } from './enhancementBroadcastReissue';
import { ApiErrorHandler } from '@/types/api';
import { ENHANCEMENT_PRESETS } from '@/types/domain';
import type { EnhancementPreset } from '@/types/domain';
import type { EnhancementState } from './enhancementState';

type ReissueActiveStream = (
  command: 'play_enhanced' | 'play_normal',
  options?: { preset?: EnhancementPreset; intensity?: number }
) => void;

export interface EnhancementCommandDeps {
  setState: Dispatch<SetStateAction<EnhancementState>>;
  setIsLoading: (loading: boolean) => void;
  setError: (error: ApiError | null) => void;
  /** Latest values, kept current by the caller so no command reads a stale closure. */
  enabledRef: MutableRefObject<boolean>;
  presetRef: MutableRefObject<EnhancementPreset>;
  intensityRef: MutableRefObject<number>;
  reissueRef: MutableRefObject<ReissueActiveStream>;
}

export interface EnhancementCommands {
  toggleEnabled: () => Promise<void>;
  setEnabled: (enabled: boolean) => Promise<void>;
  setPreset: (preset: EnhancementPreset) => Promise<void>;
  setIntensity: (intensity: number) => Promise<void>;
}

export function useEnhancementCommands({
  setState, setIsLoading, setError, enabledRef, presetRef, intensityRef, reissueRef,
}: EnhancementCommandDeps): EnhancementCommands {
  const { post } = useRestAPI();

  // Ref-based in-flight guard prevents rapid double-click from sending duplicate
  // requests: both clicks would read the same stale state.enabled and call the
  // API twice with the same value (fixes #2404).
  const isTogglingRef = useRef(false);

  // Monotonic request ids so overlapping setPreset/setIntensity calls (rapid
  // preset clicks / slider drags) apply state from whichever call was
  // dispatched LAST, not whichever *resolves* last (fixes #4339 — unlike
  // isTogglingRef, these must allow overlap, so a counter rather than a
  // boolean guard).
  // Overlapping commands share one isLoading flag: it clears when the LAST one settles, not when
  // a superseded call's finally runs while a newer POST is still in flight (#6042).
  const pendingCommandsRef = useRef(0);
  const beginLoading = useCallback(() => {
    pendingCommandsRef.current += 1;
    setIsLoading(true);
  }, [setIsLoading]);
  const endLoading = useCallback(() => {
    pendingCommandsRef.current = Math.max(0, pendingCommandsRef.current - 1);
    if (pendingCommandsRef.current === 0) setIsLoading(false);
  }, [setIsLoading]);
  const presetRequestIdRef = useRef(0);
  const intensityRequestIdRef = useRef(0);

  const toggleEnabled = useCallback(async (): Promise<void> => {
    if (isTogglingRef.current) return;
    isTogglingRef.current = true;
    beginLoading();
    setError(null);

    const newEnabled = !enabledRef.current;

    try {
      await post('/api/player/enhancement/toggle', { enabled: newEnabled });

      // Optimistic update - server will broadcast confirmation via WebSocket
      setState((prevState) => ({
        ...prevState,
        enabled: newEnabled,
        lastUpdated: Date.now(),
      }));

      // #3759: re-issue the active stream as the appropriate type so the
      // user keeps hearing audio after the toggle. The backend's
      // `stream_enhanced_audio` loop sees enabled=false and breaks, so the
      // old stream ends here regardless — switching stream type is required
      // behaviour, not a workaround.
      //
      // #4659 re-grounded the signal this compensates for: that terminal
      // `audio_stream_end` now carries `reason: 'stopped'` and reports the
      // samples actually delivered, so a consumer can distinguish it from a
      // finished track instead of seeing a success-shaped completion.
      if (newEnabled) {
        markLocalEnhancementCommand();
        reissueRef.current('play_enhanced', {
          preset: presetRef.current,
          intensity: intensityRef.current,
        });
      } else {
        markLocalEnhancementCommand();
        reissueRef.current('play_normal');
      }
    } catch (err) {
      const apiError = ApiErrorHandler.parseWithCode(err, 'TOGGLE_ERROR');

      setError(apiError);
      throw apiError;
    } finally {
      isTogglingRef.current = false;
      endLoading();
    }
  }, [post, beginLoading, endLoading]);

  /**
   * Set enhancement enabled/disabled explicitly
   */
  const setEnabled = useCallback(async (enabled: boolean): Promise<void> => {
    // Only toggle if the requested state differs from current
    if (enabledRef.current === enabled) return;
    await toggleEnabled();
  }, [toggleEnabled]);

  /**
   * Change enhancement preset
   *
   * @param preset New preset (only 'adaptive' is valid)
   * @throws Error if preset change fails
   */
  const setPreset = useCallback(async (preset: EnhancementPreset): Promise<void> => {
    beginLoading();
    setError(null);

    // Validate preset. EnhancementPreset is now a single-member literal type
    // ('adaptive' -- #4861 follow-up), so this can only fail for a caller
    // that bypasses the type via `as` or an untyped source (e.g. a
    // WebSocket message); kept as a runtime guard for exactly that case.
    if (!ENHANCEMENT_PRESETS.includes(preset)) {
      const apiError = {
        message: `Invalid preset: ${preset}`,
        code: 'INVALID_PRESET',
        status: 400,
      };
      setError(apiError);
      endLoading();
      throw apiError;
    }

    // #4339: capture this call's id before awaiting so a later, overlapping
    // setPreset call can supersede it.
    const requestId = ++presetRequestIdRef.current;

    try {
      await post('/api/player/enhancement/preset', { preset });

      // A newer setPreset call was dispatched while this POST was in
      // flight — its own resolution is authoritative, not this stale one.
      // Prevents out-of-order resolution from clobbering the UI with an
      // older preset (#4339).
      if (requestId !== presetRequestIdRef.current) return;

      // Optimistic update - server will broadcast confirmation via WebSocket
      setState((prevState) => ({
        ...prevState,
        preset,
        lastUpdated: Date.now(),
      }));

      // #3763: ChunkedAudioProcessor binds preset/intensity at construction,
      // so live changes need a stream restart from the current position.
      // Only re-issue when enhancement is currently enabled — when it's
      // off, the user is on play_normal and preset/intensity don't affect
      // the audio path.
      if (enabledRef.current) {
        markLocalEnhancementCommand();
        reissueRef.current('play_enhanced', {
          preset,
          intensity: intensityRef.current,
        });
      }
    } catch (err) {
      if (requestId !== presetRequestIdRef.current) return;

      const apiError = ApiErrorHandler.parseWithCode(err, 'PRESET_ERROR');

      setError(apiError);
      throw apiError;
    } finally {
      endLoading();
    }
  }, [post, beginLoading, endLoading]);

  /**
   * Adjust enhancement intensity
   *
   * @param intensity Intensity level 0.0-1.0
   * @throws Error if intensity change fails
   */
  const setIntensity = useCallback(async (intensity: number): Promise<void> => {
    beginLoading();
    setError(null);

    // Clamp intensity to valid range. Reject non-finite input outright (#4600):
    // Math.max/Math.min propagate NaN rather than clamping it, so a NaN would
    // survive to JSON.stringify — which serialises it as `null` — and come back
    // as an opaque 422. The server rejects out-of-range values now instead of
    // silently clamping, so the client must not send something it cannot mean.
    if (!Number.isFinite(intensity)) {
      const apiError: ApiError = {
        status: 422,
        message: 'Intensity must be a finite number between 0.0 and 1.0',
        code: 'INVALID_INTENSITY',
      };
      setError(apiError);
      endLoading();
      throw apiError;
    }
    const validIntensity = Math.max(0.0, Math.min(1.0, intensity));

    // #4339: capture this call's id before awaiting so a later, overlapping
    // setIntensity call (e.g. the next tick of a slider drag) can supersede
    // it — collapses a rapid-drag burst to a single applied value/reissue
    // instead of one per intermediate value.
    const requestId = ++intensityRequestIdRef.current;

    try {
      await post('/api/player/enhancement/intensity', { intensity: validIntensity });

      // A newer setIntensity call was dispatched while this POST was in
      // flight — its own resolution is authoritative, not this stale one.
      if (requestId !== intensityRequestIdRef.current) return;

      // Optimistic update - server will broadcast confirmation via WebSocket
      setState((prevState) => ({
        ...prevState,
        intensity: validIntensity,
        lastUpdated: Date.now(),
      }));

      // #3763: live intensity changes require stream restart — see setPreset.
      if (enabledRef.current) {
        markLocalEnhancementCommand();
        reissueRef.current('play_enhanced', {
          preset: presetRef.current,
          intensity: validIntensity,
        });
      }
    } catch (err) {
      if (requestId !== intensityRequestIdRef.current) return;

      const apiError = ApiErrorHandler.parseWithCode(err, 'INTENSITY_ERROR');

      setError(apiError);
      throw apiError;
    } finally {
      endLoading();
    }
  }, [post, beginLoading, endLoading]);

  return { toggleEnabled, setEnabled, setPreset, setIntensity };
}
