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
import { useLatestRequestGuard } from '@/hooks/shared/useLatestRequestGuard';
import type { ApiError } from '@/types/api';
import { beginLocalEnhancementCommand } from './enhancementBroadcastReissue';
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
  const beginPresetRequest = useLatestRequestGuard();
  const beginIntensityRequest = useLatestRequestGuard();

  /**
   * Run one command: POST it, apply the result optimistically (the server confirms over the
   * WebSocket), and map a failure to an ApiError. `isStale` (preset/intensity only) reports that a
   * newer call of the same kind was dispatched while this POST was in flight - then its own
   * resolution is authoritative and neither this success nor this failure is applied (#4339).
   */
  const runCommand = useCallback(
    async (spec: {
      errorCode: string;
      request: () => Promise<unknown>;
      apply: () => void;
      isStale?: () => boolean;
    }): Promise<void> => {
      beginLoading();
      setError(null);
      // Before the request: the server broadcasts the change before it answers the POST, so the
      // echo can arrive first and must already read as this client's own (#6572).
      const endLocalCommand = beginLocalEnhancementCommand();
      let succeeded = false;
      try {
        await spec.request();
        succeeded = true;
        if (spec.isStale?.()) return;
        spec.apply();
      } catch (err) {
        if (spec.isStale?.()) return;
        const apiError = ApiErrorHandler.parseWithCode(err, spec.errorCode);
        setError(apiError);
        throw apiError;
      } finally {
        endLocalCommand(succeeded);
        endLoading();
      }
    },
    [beginLoading, endLoading, setError]
  );

  const reportInvalid = useCallback(
    (apiError: ApiError): never => {
      setError(apiError);
      throw apiError;
    },
    [setError]
  );

  /** Merge a change into the state, stamping lastUpdated. */
  const applyState = useCallback(
    (change: Partial<EnhancementState>) =>
      setState((prevState) => ({ ...prevState, ...change, lastUpdated: Date.now() })),
    [setState]
  );

  /** #3763: ChunkedAudioProcessor binds preset/intensity at construction, so a live change needs a
   *  stream restart from the current position. */
  const reissueEnhanced = useCallback(
    (preset: EnhancementPreset, intensity: number) => {
      reissueRef.current('play_enhanced', { preset, intensity });
    },
    [reissueRef]
  );

  const toggleEnabled = useCallback(async (): Promise<void> => {
    if (isTogglingRef.current) return;
    isTogglingRef.current = true;
    const newEnabled = !enabledRef.current;
    try {
      await runCommand({
        errorCode: 'TOGGLE_ERROR',
        request: () => post('/api/player/enhancement/toggle', { enabled: newEnabled }),
        apply: () => {
          applyState({ enabled: newEnabled });
          // #3759: re-issue the active stream as the appropriate type so the user keeps hearing
          // audio after the toggle. The backend's stream_enhanced_audio loop sees enabled=false
          // and breaks, so the old stream ends here regardless - switching stream type is
          // required behaviour. (#4659: that terminal audio_stream_end now carries
          // reason 'stopped', distinguishing it from a finished track.)
          if (newEnabled) {
            reissueEnhanced(presetRef.current, intensityRef.current);
          } else {
            reissueRef.current('play_normal');
          }
        },
      });
    } finally {
      isTogglingRef.current = false;
    }
  }, [post, runCommand, applyState, reissueEnhanced, enabledRef, presetRef, intensityRef, reissueRef]);

  /** Set enhancement enabled/disabled explicitly; only toggles if the requested state differs. */
  const setEnabled = useCallback(async (enabled: boolean): Promise<void> => {
    if (enabledRef.current === enabled) return;
    await toggleEnabled();
  }, [toggleEnabled, enabledRef]);

  /** Change the preset (only 'adaptive' is valid). */
  const setPreset = useCallback(async (preset: EnhancementPreset): Promise<void> => {
    // EnhancementPreset is a single-member literal type ('adaptive', #4861 follow-up), so this can
    // only fail for a caller that bypasses the type (`as`, or an untyped WebSocket message).
    if (!ENHANCEMENT_PRESETS.includes(preset)) {
      reportInvalid({ message: `Invalid preset: ${preset}`, code: 'INVALID_PRESET', status: 400 });
    }
    await runCommand({
      errorCode: 'PRESET_ERROR',
      // Captured before awaiting so a later, overlapping setPreset can supersede this one (#4339).
      isStale: beginPresetRequest(),
      request: () => post('/api/player/enhancement/preset', { preset }),
      apply: () => {
        applyState({ preset });
        // Only when enhancement is on: otherwise the user is on play_normal and preset/intensity
        // do not affect the audio path.
        if (enabledRef.current) reissueEnhanced(preset, intensityRef.current);
      },
    });
  }, [post, runCommand, reportInvalid, applyState, reissueEnhanced, beginPresetRequest, enabledRef, intensityRef]);

  /** Adjust the intensity, 0.0-1.0. */
  const setIntensity = useCallback(async (intensity: number): Promise<void> => {
    // Reject non-finite input outright (#4600): Math.max/Math.min propagate NaN rather than
    // clamping it, so a NaN would survive to JSON.stringify - which serialises it as `null` - and
    // come back as an opaque 422. The server rejects out-of-range values now instead of silently
    // clamping, so the client must not send something it cannot mean.
    if (!Number.isFinite(intensity)) {
      reportInvalid({
        status: 422,
        message: 'Intensity must be a finite number between 0.0 and 1.0',
        code: 'INVALID_INTENSITY',
      });
    }
    const validIntensity = Math.max(0.0, Math.min(1.0, intensity));
    await runCommand({
      errorCode: 'INTENSITY_ERROR',
      // Captured before awaiting: the next tick of a slider drag supersedes this call, collapsing a
      // rapid-drag burst to one applied value/reissue instead of one per intermediate value (#4339).
      isStale: beginIntensityRequest(),
      request: () => post('/api/player/enhancement/intensity', { intensity: validIntensity }),
      apply: () => {
        applyState({ intensity: validIntensity });
        if (enabledRef.current) reissueEnhanced(presetRef.current, validIntensity);
      },
    });
  }, [post, runCommand, reportInvalid, applyState, reissueEnhanced, beginIntensityRequest, enabledRef, presetRef]);

  return { toggleEnabled, setEnabled, setPreset, setIntensity };
}
