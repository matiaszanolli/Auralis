/**
 * useAudioPlayback - Audio Playback Management Hook
 *
 * Handles audio element lifecycle, stream URL generation, and playback state.
 * Supports both HTML5 audio (legacy) and MSE (progressive streaming).
 *
 * Features:
 * - Audio element refs management
 * - Stream URL generation with enhancement parameters
 * - MSE vs HTML5 mode switching
 * - Track loading with position restoration
 * - Playback state synchronization
 * - Volume control
 */

import { useRef, useEffect, useState, useCallback } from 'react';
import { useMSEController } from './useMSEController';
import { calculateTotalChunks, getChunkIndexForTime } from '../services/mseStreamingService';

interface Track {
  id: number;
  title: string;
  artist?: string;
  favorite?: boolean;
  // ... other track properties
}

interface EnhancementSettings {
  enabled: boolean;
  preset: string;
  intensity: number;
}

interface UseAudioPlaybackOptions {
  currentTrack: Track | null;
  isPlaying: boolean;
  enhancementSettings: EnhancementSettings;
  useMSE?: boolean; // Enable MSE progressive streaming
  onTimeUpdate?: (currentTime: number) => void;
  onEnded?: () => void;
}

interface UseAudioPlaybackReturn {
  // Audio element refs
  audioRef: React.RefObject<HTMLAudioElement>;
  nextAudioRef: React.RefObject<HTMLAudioElement>;

  // State
  isBuffering: boolean;
  currentTime: number;
  totalChunks: number;

  // Methods
  loadTrack: (trackId: number, preset: string, intensity: number) => Promise<void>;
  switchPreset: (preset: string, intensity: number) => Promise<void>;
  play: () => Promise<void>;
  pause: () => void;
  setVolume: (volume: number) => void;

  // MSE-specific
  mseReady: boolean;
  mseError: string | null;
}

/**
 * Audio Playback Hook
 *
 * Manages audio elements and playback state with support for both
 * HTML5 audio (legacy) and MSE (progressive streaming).
 */
export function useAudioPlayback(options: UseAudioPlaybackOptions): UseAudioPlaybackReturn {
  const {
    currentTrack,
    isPlaying,
    enhancementSettings,
    useMSE = false,
    onTimeUpdate,
    onEnded
  } = options;

  // Audio element refs (for both HTML5 and MSE modes)
  const audioRef = useRef<HTMLAudioElement>(null);
  const nextAudioRef = useRef<HTMLAudioElement>(null);

  // Local state
  const [isBuffering, setIsBuffering] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [totalChunks, setTotalChunks] = useState(0);
  const lastLoadedTrackId = useRef<number | null>(null);

  // MSE controller (only initialized if useMSE=true)
  const mse = useMSEController();

  /**
   * Generate stream URL for HTML5 audio mode
   */
  const generateStreamUrl = useCallback((trackId: number, preset: string, intensity: number, enhanced: boolean): string => {
    const params = new URLSearchParams();
    if (enhanced) {
      params.append('enhanced', 'true');
      params.append('preset', preset);
      params.append('intensity', intensity.toString());
    }
    return `http://localhost:8765/api/player/stream/${trackId}${params.toString() ? '?' + params.toString() : ''}`;
  }, []);

  /**
   * Initialize MSE on mount (if enabled)
   */
  useEffect(() => {
    console.log(`🔍 MSE Init Effect: useMSE=${useMSE}, isSupported=${mse.isSupported}, audioRef=${!!audioRef.current}`);

    if (!useMSE) {
      console.log('⏭️ MSE disabled, skipping initialization');
      return;
    }

    // Give MSE controller time to initialize (race condition fix)
    const initTimer = setTimeout(() => {
      if (!mse.isSupported) {
        console.log('⏭️ MSE not supported after waiting, skipping initialization');
        return;
      }

      if (!audioRef.current) {
        console.log('⚠️ Audio element not ready, will retry when available');
        return;
      }

      console.log('🚀 Initializing MSE...');
      const objectUrl = mse.initializeMSE();
      if (objectUrl) {
        audioRef.current.src = objectUrl;
        console.log(`✅ MSE initialized for audio playback, object URL: ${objectUrl}`);
      } else {
        console.error('❌ Failed to get MSE object URL');
      }
    }, 100); // Wait 100ms for MSE controller to initialize

    return () => clearTimeout(initTimer);
  }, [useMSE, mse.isSupported]); // Removed mse.initializeMSE from deps to prevent re-runs

  /**
   * Load track into audio element
   *
   * For HTML5 mode: Sets audio.src to stream URL
   * For MSE mode: Loads first chunk and starts progressive loading
   */
  const loadTrack = useCallback(async (trackId: number, preset: string, intensity: number) => {
    if (!audioRef.current) return;

    const isSameTrack = lastLoadedTrackId.current === trackId;
    const savedPosition = isSameTrack ? audioRef.current.currentTime : 0;
    const wasPlaying = isSameTrack && !audioRef.current.paused;

    try {
      setIsBuffering(true);

      // Debug: Log MSE status
      console.log(`🔍 MSE Status: useMSE=${useMSE}, isSupported=${mse.isSupported}, isReady=${mse.isReady}`);

      if (useMSE && mse.isReady) {
        // MSE Mode: Load first chunk
        console.log('✅ MSE: Using progressive streaming');
        console.log(`🎵 MSE: Loading first chunk for track ${trackId}`);

        // Clear previous buffer
        await mse.clearBuffer();

        // Load first chunk
        const success = await mse.loadChunk({
          trackId,
          chunkIndex: 0,
          preset,
          intensity,
        });

        if (!success) {
          throw new Error('Failed to load first chunk');
        }

        // Calculate total chunks if duration available
        if (audioRef.current.duration) {
          const chunks = calculateTotalChunks(audioRef.current.duration);
          setTotalChunks(chunks);
        }

      } else {
        // HTML5 Mode: Load full file
        const streamUrl = generateStreamUrl(trackId, preset, intensity, enhancementSettings.enabled);

        // Check if URL unchanged
        if (audioRef.current.src === streamUrl) {
          console.log(`✅ Stream URL unchanged, skipping reload`);
          setIsBuffering(false);
          return;
        }

        console.log(`🎵 HTML5: Loading track ${trackId} from ${streamUrl}`);

        // Abort any pending load
        if (audioRef.current.src) {
          audioRef.current.pause();
          audioRef.current.removeAttribute('src');
          audioRef.current.load();
        }

        // Load new track
        audioRef.current.src = streamUrl;
        audioRef.current.load();
      }

      lastLoadedTrackId.current = trackId;

      // Restore position if same track
      if (isSameTrack && savedPosition > 0) {
        const restorePlayback = () => {
          if (audioRef.current) {
            audioRef.current.currentTime = savedPosition;
            setCurrentTime(savedPosition);
            if (wasPlaying) {
              audioRef.current.play().catch(e => console.error('Failed to resume playback:', e));
            }
            audioRef.current.removeEventListener('loadedmetadata', restorePlayback);
          }
        };
        audioRef.current.addEventListener('loadedmetadata', restorePlayback);
      } else {
        setCurrentTime(0);
      }

    } catch (error) {
      console.error('Failed to load track:', error);
      throw error;
    } finally {
      setIsBuffering(false);
    }
  }, [useMSE, mse.isReady, mse.clearBuffer, mse.loadChunk, generateStreamUrl, enhancementSettings.enabled]);

  /**
   * Switch preset on current track (instant with MSE, reload with HTML5)
   */
  const switchPreset = useCallback(async (preset: string, intensity: number) => {
    if (!audioRef.current || !currentTrack) return;

    const currentPosition = audioRef.current.currentTime;
    const wasPlaying = !audioRef.current.paused;

    try {
      setIsBuffering(true);

      if (useMSE && mse.isReady) {
        // MSE Mode: Instant preset switch
        console.log(`🔄 MSE: Switching to preset ${preset}`);

        const currentChunk = getChunkIndexForTime(currentPosition);

        // Clear buffer
        await mse.clearBuffer();

        // Load new preset chunk at current position
        await mse.loadChunk({
          trackId: currentTrack.id,
          chunkIndex: currentChunk,
          preset,
          intensity,
        });

        // Restore position
        audioRef.current.currentTime = currentPosition;
        if (wasPlaying) {
          await audioRef.current.play();
        }

      } else {
        // HTML5 Mode: Reload full file
        console.log(`🔄 HTML5: Switching to preset ${preset} (requires reload)`);
        await loadTrack(currentTrack.id, preset, intensity);
      }

    } catch (error) {
      console.error('Failed to switch preset:', error);
      throw error;
    } finally {
      setIsBuffering(false);
    }
  }, [useMSE, mse.isReady, mse.clearBuffer, mse.loadChunk, currentTrack, loadTrack]);

  /**
   * Play audio
   */
  const play = useCallback(async () => {
    if (!audioRef.current) return;

    try {
      await audioRef.current.play();
      console.log('▶️ Playback started');
    } catch (error) {
      console.error('Failed to play:', error);
      // Try reloading if play fails
      if (currentTrack) {
        console.log('Retrying playback after error...');
        audioRef.current.load();
        setTimeout(() => {
          audioRef.current?.play().catch(e => console.error('Retry failed:', e));
        }, 100);
      }
    }
  }, [currentTrack]);

  /**
   * Pause audio
   */
  const pause = useCallback(() => {
    if (!audioRef.current) return;
    audioRef.current.pause();
    console.log('⏸️ Playback paused');
  }, []);

  /**
   * Set volume on both audio elements
   */
  const setVolume = useCallback((volume: number) => {
    const normalizedVolume = Math.max(0, Math.min(100, volume)) / 100;

    if (audioRef.current) {
      audioRef.current.volume = normalizedVolume;
    }
    if (nextAudioRef.current) {
      nextAudioRef.current.volume = normalizedVolume;
    }
  }, []);

  /**
   * Load new track when currentTrack or enhancement settings change
   */
  useEffect(() => {
    if (!currentTrack) return;

    loadTrack(
      currentTrack.id,
      enhancementSettings.preset,
      enhancementSettings.intensity
    ).catch(error => {
      console.error('Failed to load track on change:', error);
    });
  }, [currentTrack, enhancementSettings.preset, enhancementSettings.intensity, loadTrack]);

  /**
   * Sync HTML5 audio element with backend isPlaying state
   */
  useEffect(() => {
    if (!audioRef.current || !currentTrack) return;

    if (isPlaying && audioRef.current.paused && audioRef.current.src) {
      console.log('🎵 Backend playing but HTML5 paused - starting playback');
      play().catch(e => console.error('Failed to auto-play from backend state:', e));
    }

    if (!isPlaying && !audioRef.current.paused) {
      console.log('⏸️ Backend paused but HTML5 playing - pausing playback');
      pause();
    }
  }, [isPlaying, currentTrack, play, pause]);

  /**
   * Handle time updates
   */
  useEffect(() => {
    if (!audioRef.current) return;

    const handleTimeUpdate = () => {
      if (!audioRef.current) return;

      const time = audioRef.current.currentTime;
      setCurrentTime(time);

      // Update MSE current chunk
      if (useMSE && mse.isReady) {
        mse.updateCurrentChunk(time);
      }

      // Notify parent
      if (onTimeUpdate) {
        onTimeUpdate(time);
      }
    };

    audioRef.current.addEventListener('timeupdate', handleTimeUpdate);

    return () => {
      audioRef.current?.removeEventListener('timeupdate', handleTimeUpdate);
    };
  }, [useMSE, mse.isReady, mse.updateCurrentChunk, onTimeUpdate]);

  /**
   * Handle track end
   */
  useEffect(() => {
    if (!audioRef.current) return;

    const handleEnded = () => {
      console.log('🎵 Track ended');
      if (onEnded) {
        onEnded();
      }
    };

    audioRef.current.addEventListener('ended', handleEnded);

    return () => {
      audioRef.current?.removeEventListener('ended', handleEnded);
    };
  }, [onEnded]);

  return {
    // Refs
    audioRef,
    nextAudioRef,

    // State
    isBuffering,
    currentTime,
    totalChunks,

    // Methods
    loadTrack,
    switchPreset,
    play,
    pause,
    setVolume,

    // MSE-specific
    mseReady: mse.isReady,
    mseError: mse.error,
  };
}
