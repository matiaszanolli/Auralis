/**
 * Player Service Types
 *
 * Shared types and interfaces for decomposed player services
 */

export interface TimeUpdateEvent {
  currentTime: number;
  duration: number;
}

export interface TimingDebugInfo {
  time: number;
  audioCtxTime: number;
  trackStartTime: number;
  difference: number;
}

export interface PlaybackEvent {
  state: PlaybackState;
  timestamp: number;
}

export type PlaybackState =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'playing'
  | 'paused'
  | 'buffering'
  | 'seeking'
  | 'error';

export type EventCallback = (data?: any) => void;

export interface IChunkPreloadManager {
  queueChunk(chunkIndex: number, priority: number): void;
  getQueueSize(): number;
  isLoading(chunkIndex: number): boolean;
  clearLowerPriority(priority: number): void;
  clearQueue(): void;
  initChunks(chunkCount: number): void;
  setAudioContext(audioContext: AudioContext): void;
  on(event: string, callback: EventCallback): void;
  off(event: string, callback: EventCallback): void;
  destroy(): void;
}

export interface IAudioContextController {
  ensureAudioContext(): void;
  playChunk(chunkIndex: number, audioBuffer: AudioBuffer, offset: number): Promise<void>;
  setVolume(volume: number): void;
  stopCurrentSource(): void;
  getIsPlaying(): boolean;
}

export interface ITimingEngine {
  startTimeUpdates(): void;
  stopTimeUpdates(): void;
  getCurrentTime(): number;
  getCurrentTimeDebug(): TimingDebugInfo;
  setPauseTime(time: number): void;
  updateTimingReference(audioCtxTime: number, trackTime: number): void;
  on(event: 'timeupdate', callback: EventCallback): void;
}

export interface IPlaybackController {
  play(): Promise<void>;
  pause(): void;
  seek(time: number): Promise<void>;
  getState(): PlaybackState;
  setState(newState: PlaybackState): void;
}
