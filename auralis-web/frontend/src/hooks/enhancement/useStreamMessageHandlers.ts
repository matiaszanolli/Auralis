/**
 * Stream message handlers for useAudioStreamingCore.
 *
 * The chunk/end/error handling glue, moved verbatim out of
 * useAudioStreamingCore.ts (#5478, continuing #5041's extraction of the pure
 * arithmetic into audioChunkIngest.ts). What stays here is acting on the
 * ingest decisions, because that needs the refs, the dispatcher and the
 * socket; the subscription wiring that forwards frames into these handlers
 * lives in ./useStreamSubscriptions.
 *
 * @module hooks/enhancement/useStreamMessageHandlers
 */

const DEBUG = import.meta.env.DEV;

import { useCallback } from 'react';
import { setStreamingError, completeStreaming } from '@/store/slices/playerSlice';
import { useStore } from 'react-redux';
import type { AppDispatch, RootState } from '@/store';
import { endActiveStream } from '@/hooks/websocket/websocketConnectionState';
import type { useWebSocketContext } from '@/contexts/WebSocketContext';
import type {
  AudioChunkMessage,
  AudioStreamEndMessage,
  AudioStreamErrorMessage,
} from '@/contexts/WebSocketContext';
import type { PCMStreamBuffer } from '@/services/audio/PCMStreamBuffer';
import type { AudioPlaybackEngine } from '@/services/audio/AudioPlaybackEngine';
import type { StreamingMetadata, StreamType } from './streamingCoreTypes';
import { useStreamChunkHandler } from './useStreamChunkHandler';

/** Everything the handlers and the subscription effect act on. The refs are
 *  owned by the parent (they are part of StreamingCoreReturn); the handler
 *  refs live here because nothing outside this hook reads them. */
export interface StreamMessageHandlerDeps {
  wsContext: ReturnType<typeof useWebSocketContext>;
  dispatch: AppDispatch;

  streamType: StreamType;
  logPrefix: string;
  throttleProgress: boolean;
  detectOutOfSequence: boolean;

  // Shared refs (parent-owned)
  pcmBufferRef: React.MutableRefObject<PCMStreamBuffer | null>;
  playbackEngineRef: React.MutableRefObject<AudioPlaybackEngine | null>;
  pendingChunksRef: React.MutableRefObject<AudioChunkMessage[]>;
  streamingMetadataRef: React.MutableRefObject<StreamingMetadata | null>;
  lastReceivedChunkIndexRef: React.MutableRefObject<number>;
  lastDispatchedProgressRef: React.MutableRefObject<number>;
  flowPausedRef: React.MutableRefObject<boolean>;
  /** Epoch of the stream the current audio_stream_start opened (#4563);
   *  owned by the parent, read here by the chunk classifier. */
  streamEpochRef: React.MutableRefObject<number | null>;
  /** Bounds handleStreamError's auto-resume to one attempt per distinct
   *  (trackId, recovery_position) pair (#4655). */
  lastRecoveryAttemptRef: React.MutableRefObject<{ trackId: number; position: number } | null>;

  // Parent callbacks
  acceptsStreamType: (incoming: StreamType | undefined) => boolean;
  startPlaybackWhenBuffered: () => void;
  cleanupStreaming: () => void;
  setCurrentTime: React.Dispatch<React.SetStateAction<number>>;
}

export function useStreamMessageHandlers(deps: StreamMessageHandlerDeps) {
  const {
    wsContext,
    dispatch,
    streamType,
    logPrefix,
    playbackEngineRef,
    lastRecoveryAttemptRef,
    acceptsStreamType,
    startPlaybackWhenBuffered,
    cleanupStreaming,
  } = deps;

  const store = useStore<RootState>();
  // True for a stream-level message naming a track other than the one this
  // stream is playing: a late end/error from a superseded track after a rapid
  // skip must not tear down or mark the NEW track's stream (#6017). The reducer
  // already drops such actions; this keeps the side effects from running too.
  const isSupersededTrack = useCallback((trackId: number | undefined): boolean => {
    const active = store.getState().player.streaming[streamType].trackId;
    return trackId != null && active != null && active !== trackId;
  }, [store, streamType]);

  const handleChunk = useStreamChunkHandler(deps);

  const handleStreamEnd = useCallback((message: AudioStreamEndMessage) => {
    // Only process messages intended for this stream (#2104)
    if (!acceptsStreamType(message.data.stream_type)) return;

    // A backend older than #4659 sends no reason, and its end always meant completion.
    const reason = message.data.reason ?? 'completed';
    const trackId = message.data.track_id;
    if (isSupersededTrack(trackId)) return;

    DEBUG && console.log(`${logPrefix} Stream ended:`, {
      trackId,
      reason,
      totalSamples: message.data.total_samples,
      duration: message.data.duration,
    });

    // Whatever the reason, a stream that ended by finishing (or finishing with
    // gaps) has sent all it will: let the engine play out the buffered tail
    // instead of holding it under the low-water mark. 'stopped' is a superseded
    // stream, whose engine is replaced or reset anyway.
    if (reason === 'completed' || reason === 'errored') {
      playbackEngineRef.current?.markStreamEnded();
      // A stream shorter than the start threshold never auto-started; its end is the last
      // chance to play what it delivered (#5900).
      startPlaybackWhenBuffered();
      // The backend has sent all it will, so neither a reconnect nor an
      // enhancement toggle may restart this track (#5876). The buffered tail
      // keeps playing in its current mode.
      endActiveStream(trackId);
    }

    // #5462: only a stream that delivered the whole track is complete. Marking
    // an early exit 'complete' showed 100% progress and fed the session's
    // auto-advance, which keys off that state.
    if (reason === 'completed') {
      // Pass track_id so a stale 'end' from a superseded track after a rapid
      // skip doesn't prematurely mark the new track complete (#4434).
      dispatch(completeStreaming({ streamType, trackId }));
    } else if (reason === 'errored') {
      // The loop reached the end but skipped chunks — each already reported via
      // audio_stream_error. Keep the stream in error rather than 'complete'.
      dispatch(setStreamingError({
        streamType,
        trackId,
        error: 'Playback ended with gaps: part of this track could not be processed',
      }));
    }
    // 'stopped': whatever stopped it supersedes it — a new play command, or the
    // play_normal re-issue that disabling enhancement sends — so nothing to record.
  }, [dispatch, streamType, logPrefix, acceptsStreamType, playbackEngineRef, isSupersededTrack, startPlaybackWhenBuffered]);

  const handleStreamError = useCallback((message: AudioStreamErrorMessage) => {
    // Only process messages intended for this stream (#2104)
    if (!acceptsStreamType(message.data.stream_type)) return;
    if (isSupersededTrack(message.data.track_id)) return;

    const errorMsg = `Streaming error: ${message.data.error} (${message.data.code})`;

    // #5867: the backend skipped this chunk and keeps streaming (#3190). Tearing
    // down here ended audible playback at the bad chunk while the rest of the
    // track arrived with nowhere to go. Keep the engine and buffer; the gap is
    // reported by the closing audio_stream_end{reason:'errored'}.
    if (message.data.continues === true) {
      console.warn(logPrefix, `${errorMsg}; chunk skipped, stream continues`);
      return;
    }

    console.error(logPrefix, errorMsg);
    // Pass track_id so a stale error from a superseded track after a rapid
    // skip isn't shown on the new track (#4434).
    dispatch(setStreamingError({ streamType, error: errorMsg, trackId: message.data.track_id }));
    cleanupStreaming();

    // #4655: when the backend names a safe resume offset, auto-resume the
    // stream from there instead of leaving playback dead after a mid-stream
    // chunk failure. Bounded to one attempt per distinct (trackId,
    // recovery_position) pair — a persistently failing chunk would otherwise
    // keep re-arriving with the SAME recovery_position and loop forever.
    const { recovery_position: recoveryPosition, track_id: trackId } = message.data;
    const alreadyAttempted =
      lastRecoveryAttemptRef.current?.trackId === trackId &&
      lastRecoveryAttemptRef.current?.position === recoveryPosition;

    if (typeof recoveryPosition === 'number' && Number.isFinite(recoveryPosition) && !alreadyAttempted) {
      lastRecoveryAttemptRef.current = { trackId, position: recoveryPosition };
      // message.data.stream_type is the PRODUCER's label (absent on some
      // error paths) — 'normal' means play_normal, everything else
      // (including undefined, since the enhanced/seek paths are this
      // stream's default) re-issues as play_enhanced.
      const reissueType = message.data.stream_type === 'normal' ? 'play_normal' : 'play_enhanced';
      const reissued = wsContext.reissueActiveStreamAs(reissueType, {}, recoveryPosition);
      if (reissued) {
        DEBUG && console.log(
          `${logPrefix} Auto-resuming from recovery_position=${recoveryPosition}s after chunk failure`
        );
        return;
      }
    }
    // Terminal: no recovery point, or it was already tried (#5876).
    endActiveStream(trackId);
  }, [dispatch, streamType, logPrefix, cleanupStreaming, acceptsStreamType, wsContext, lastRecoveryAttemptRef, isSupersededTrack]);

  return { handleChunk, handleStreamEnd, handleStreamError };
}
