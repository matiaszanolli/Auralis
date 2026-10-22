/**
 * Hooks extracted from PlaybackSessionProvider (#5840) so the provider stays
 * wiring: the single-flight transport command gate, the start-track retry
 * (#5613), and the end-of-track auto-advance / repeat handling (#5605).
 *
 * @module contexts/usePlaybackSessionHooks
 */

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';

type TransportCommand = () => void | Promise<void>;

export interface TransportCommandGate {
  /** Resolves true when the command ran, false when dropped (another pending). */
  runTransportCommand: (command: TransportCommand) => Promise<boolean>;
  pendingCommandRef: MutableRefObject<Promise<void> | null>;
  isCommandPending: boolean;
}

/**
 * Single-flight gate for transport commands.
 *
 * The ref closes the gap before React can render disabled controls. This
 * coalesces double-clicks and keyboard repeats into the first command while
 * its playback request is still pending (#4835). Returns whether the command
 * started (false = dropped because another is pending) — user-initiated track
 * selection must react to a drop, transport next/previous treat coalescing as
 * the desired behaviour (#5613).
 */
export function useTransportCommand(): TransportCommandGate {
  const commandPendingRef = useRef(false);
  const pendingCommandRef = useRef<Promise<void> | null>(null);
  const [isCommandPending, setIsCommandPending] = useState(false);

  const runTransportCommand = useCallback(async (command: TransportCommand): Promise<boolean> => {
    if (commandPendingRef.current) return false;

    commandPendingRef.current = true;
    setIsCommandPending(true);
    const execution = (async () => {
      try {
        await command();
      } finally {
        commandPendingRef.current = false;
        setIsCommandPending(false);
      }
    })();
    pendingCommandRef.current = execution;
    try {
      await execution;
    } finally {
      if (pendingCommandRef.current === execution) pendingCommandRef.current = null;
    }
    return true;
  }, []);

  return { runTransportCommand, pendingCommandRef, isCommandPending };
}

/**
 * startTrack with one retry (#5613): by the time it runs, the queue POST for
 * this track has already succeeded — silently dropping the start left the
 * backend queue on this track while the previous one kept playing. Wait out
 * the in-flight command and retry once.
 */
export function useStartTrackRetry(
  gate: Pick<TransportCommandGate, 'runTransportCommand' | 'pendingCommandRef'>,
  startTrackForSettings: (trackId: number) => void | Promise<void>
): (trackId: number) => Promise<void> {
  const { runTransportCommand, pendingCommandRef } = gate;
  return useCallback(
    async (trackId: number) => {
      const started = await runTransportCommand(() => startTrackForSettings(trackId));
      if (started) return;

      await pendingCommandRef.current;
      await runTransportCommand(() => startTrackForSettings(trackId));
    },
    [runTransportCommand, pendingCommandRef, startTrackForSettings]
  );
}

export interface AutoAdvanceInputs {
  streamingState: string;
  currentTime: number;
  trackDuration: number;
  repeatMode: string;
  currentTrackId: number | null | undefined;
  currentQueueIndex: number;
  queueLength: number;
  startTrack: (trackId: number) => Promise<void>;
  handleNext: () => Promise<void>;
}

/**
 * Auto-advance to the next queue track once streaming completes near the end
 * of the current one. Lives in the session (not in Player.tsx) so it keeps
 * working regardless of which UI is mounted — the session is the source of
 * truth, not a side effect of one component's render tree.
 */
export function useAutoAdvance({
  streamingState, currentTime, trackDuration, repeatMode, currentTrackId,
  currentQueueIndex, queueLength, startTrack, handleNext,
}: AutoAdvanceInputs): void {
  const hasAutoAdvancedRef = useRef(false);

  // Reset the auto-advance latch when a new track starts OR playback leaves
  // the completed state — the repeat-'one' restart (#5605) re-plays the same
  // id, so the id-change reset alone would leave the latch stuck set.
  // Resetting only while NOT complete preserves the one-trigger-per-completion
  // guard: during a single completion window the state stays 'complete'.
  useEffect(() => {
    if (streamingState !== 'complete') {
      hasAutoAdvancedRef.current = false;
    }
  }, [currentTrackId, streamingState]);

  useEffect(() => {
    const isComplete = streamingState === 'complete';
    const nearEnd = trackDuration > 0 && currentTime >= trackDuration - 0.5;
    if (!isComplete || !nearEnd || hasAutoAdvancedRef.current) return;

    // #5605: repeat 'one' restarts the current track at its beginning;
    // otherwise advance, wrapping to index 0 under repeat 'all' (handleNext
    // owns the wrap). repeat 'off' keeps the old behaviour: the queue ends.
    if (repeatMode === 'one') {
      if (currentTrackId == null) return;
      hasAutoAdvancedRef.current = true;
      startTrack(currentTrackId);
      return;
    }

    const hasMoreTracks = currentQueueIndex < queueLength - 1;
    if (hasMoreTracks || (repeatMode === 'all' && queueLength > 0)) {
      hasAutoAdvancedRef.current = true;
      handleNext();
    }
  }, [streamingState, currentTime, trackDuration, currentQueueIndex, queueLength, repeatMode, currentTrackId, startTrack, handleNext]);
}
