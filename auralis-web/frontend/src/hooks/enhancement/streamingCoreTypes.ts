/**
 * Shared types for the PCM streaming core (#5478, continuing #5041's
 * extraction). Split out of useAudioStreamingCore.ts so the hook file holds
 * only hook logic; useAudioStreamingCore re-exports these for its existing
 * importers.
 *
 * @module hooks/enhancement/streamingCoreTypes
 */

import type PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import type AudioPlaybackEngine from '@/services/audio/AudioPlaybackEngine';
import type {
  AudioStreamStartMessage,
  AudioChunkMessage,
  AudioStreamEndMessage,
  AudioStreamErrorMessage,
} from '@/contexts/WebSocketContext';

export interface StreamingMetadata {
  sampleRate: number;
  channels: number;
  totalChunks: number;
  processedChunks: number;
}

export type StreamType = 'normal' | 'enhanced';

export interface StreamingCoreOptions {
  /** Redux streaming slice this stream drives ('normal' | 'enhanced'). */
  streamType: StreamType;
  /** Let one shared session consume normal PCM as well as enhanced PCM. */
  acceptNormalStream?: boolean;
  /** Key used for `wsContext.setResumePositionGetter` (e.g. 'play_normal'). */
  sendType: string;
  /** Console log prefix, e.g. '[usePlayNormal]'. */
  logPrefix: string;
  /** Buffered-sample threshold at which playback auto-starts. */
  getStartThreshold: (metadata: StreamingMetadata, engine: AudioPlaybackEngine) => number;
  /** Enhanced-only: dispatch progress at most every 10% instead of every chunk (#2535). */
  throttleProgress: boolean;
  /** Enhanced-only: detect and recover from out-of-order chunks after a missed stream_start. */
  detectOutOfSequence: boolean;
  /** Normal-only: close the AudioContext on every stop/error, not just unmount. */
  closeContextOnCleanup: boolean;
  /** Extra cleanup to run at the end of cleanupStreaming() (e.g. enhanced's isSeeking reset). */
  onCleanupExtra?: () => void;
  /** Extra work to run when the WebSocket disconnects (e.g. enhanced's fingerprint-timeout clear). */
  onDisconnectExtra?: () => void;
}

export interface StreamingCoreReturn {
  // Populated by the caller every render: `handleStreamStartRef.current = handleStreamStart`.
  handleStreamStartRef: React.MutableRefObject<(message: AudioStreamStartMessage) => void>;

  // Refs the caller's handleStreamStart/start-function populate directly.
  pcmBufferRef: React.MutableRefObject<PCMStreamBuffer | null>;
  playbackEngineRef: React.MutableRefObject<AudioPlaybackEngine | null>;
  audioContextRef: React.MutableRefObject<AudioContext | null>;
  abortRef: React.MutableRefObject<AbortController | undefined>;
  pendingChunksRef: React.MutableRefObject<AudioChunkMessage[]>;
  streamingMetadataRef: React.MutableRefObject<StreamingMetadata | null>;
  flowPausedRef: React.MutableRefObject<boolean>;
  /** Epoch the ring's CURRENT content belongs to (#5861) — lags the
   * adopted stream epoch so a start can detect superseded buffer content. */
  bufferEpochRef: React.MutableRefObject<number | null>;
  lastReceivedChunkIndexRef: React.MutableRefObject<number>;
  lastDispatchedProgressRef: React.MutableRefObject<number>;
  /** Set by a user pause; while set, buffered audio never starts on its own (#5459).
   *  A new play command clears it. */
  pauseHoldRef: React.MutableRefObject<boolean>;

  currentTime: number;
  setCurrentTime: React.Dispatch<React.SetStateAction<number>>;
  isPaused: boolean;
  setIsPaused: React.Dispatch<React.SetStateAction<boolean>>;

  cleanupStreaming: () => void;
  /** Arm the first-stream-message watchdog; call right after sending a play command (#4433). */
  armStreamStartWatchdog: () => void;
  handleChunk: (message: AudioChunkMessage) => void;
  handleStreamEnd: (message: AudioStreamEndMessage) => void;
  handleStreamError: (message: AudioStreamErrorMessage) => void;
  /** Start the engine if it is idle, not held paused, and buffered past the
   *  start threshold — the single auto-start rule (#5459). */
  startPlaybackWhenBuffered: () => void;

  stopPlayback: () => void;
  pausePlayback: () => void;
  resumePlayback: () => void;
  setVolume: (volume: number) => void;
}
