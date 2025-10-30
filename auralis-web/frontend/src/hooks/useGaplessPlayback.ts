/**
 * useGaplessPlayback - Gapless Playback & Crossfade Hook
 *
 * Manages gapless playback transitions and crossfade effects between tracks.
 *
 * Features:
 * - Next track detection from queue
 * - Pre-loading logic (3s for gapless, crossfade_duration+1s for crossfade)
 * - Crossfade timing and execution
 * - Audio element switching for seamless transitions
 */

import { useRef, useEffect, useState, useCallback } from 'react';

interface Track {
  id: number;
  title: string;
  artist?: string;
  [key: string]: any;
}

interface EnhancementSettings {
  enabled: boolean;
  preset: string;
  intensity: number;
}

interface UseGaplessPlaybackOptions {
  // Audio element refs
  audioRef: React.RefObject<HTMLAudioElement>;
  nextAudioRef: React.RefObject<HTMLAudioElement>;

  // Current playback state
  currentTrack: Track | null;
  queue: Track[];
  queueIndex: number;

  // Enhancement settings
  enhancementSettings: EnhancementSettings;

  // Volume control
  volume: number;
  isMuted: boolean;

  // Callbacks
  onTrackSwitch?: () => void;
}

interface UseGaplessPlaybackReturn {
  // State
  gaplessEnabled: boolean;
  crossfadeEnabled: boolean;
  crossfadeDuration: number;
  nextTrack: Track | null;

  // Methods
  setGaplessEnabled: (enabled: boolean) => void;
  setCrossfadeEnabled: (enabled: boolean) => void;
  setCrossfadeDuration: (duration: number) => void;
}

/**
 * Gapless Playback Hook
 *
 * Handles seamless transitions between tracks with optional crossfade.
 */
export function useGaplessPlayback(options: UseGaplessPlaybackOptions): UseGaplessPlaybackReturn {
  const {
    audioRef,
    nextAudioRef,
    currentTrack,
    queue,
    queueIndex,
    enhancementSettings,
    volume,
    isMuted,
    onTrackSwitch
  } = options;

  // Gapless/crossfade settings
  const [gaplessEnabled, setGaplessEnabled] = useState(true);
  const [crossfadeEnabled, setCrossfadeEnabled] = useState(false);
  const [crossfadeDuration, setCrossfadeDuration] = useState(5.0); // seconds

  // Next track in queue
  const [nextTrack, setNextTrack] = useState<Track | null>(null);

  /**
   * Load playback settings from backend on mount
   */
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const response = await fetch('http://localhost:8765/api/settings');
        if (response.ok) {
          const settings = await response.json();
          setGaplessEnabled(settings.gapless_enabled ?? true);
          setCrossfadeEnabled(settings.crossfade_enabled ?? false);
          setCrossfadeDuration(settings.crossfade_duration ?? 5.0);
          console.log('Gapless:', settings.gapless_enabled ? 'enabled' : 'disabled');
          console.log('Crossfade:', settings.crossfade_enabled ? `enabled (${settings.crossfade_duration}s)` : 'disabled');
        }
      } catch (error) {
        console.error('Failed to load gapless settings:', error);
      }
    };
    loadSettings();
  }, []);

  /**
   * Detect next track from queue
   */
  useEffect(() => {
    if (!gaplessEnabled || !currentTrack || !queue || queue.length === 0) {
      setNextTrack(null);
      return;
    }

    const currentIndex = queueIndex || 0;
    if (currentIndex + 1 < queue.length) {
      setNextTrack(queue[currentIndex + 1]);
      console.log('📋 Next track detected:', queue[currentIndex + 1].title);
    } else {
      setNextTrack(null);
      console.log('📋 No next track (end of queue)');
    }
  }, [currentTrack, gaplessEnabled, queue, queueIndex]);

  /**
   * Generate stream URL for a track
   */
  const generateStreamUrl = useCallback((trackId: number): string => {
    const params = new URLSearchParams();
    if (enhancementSettings.enabled) {
      params.append('enhanced', 'true');
      params.append('preset', enhancementSettings.preset);
      params.append('intensity', enhancementSettings.intensity.toString());
    }
    return `http://localhost:8765/api/player/stream/${trackId}${params.toString() ? '?' + params.toString() : ''}`;
  }, [enhancementSettings]);

  /**
   * Pre-load next track when current track is near the end
   */
  useEffect(() => {
    if ((!gaplessEnabled && !crossfadeEnabled) || !nextTrack || !audioRef.current || !nextAudioRef.current) {
      return;
    }

    const checkPreload = () => {
      if (!audioRef.current) return;

      const timeRemaining = audioRef.current.duration - audioRef.current.currentTime;

      // Calculate when to pre-load based on mode:
      // - Crossfade: Pre-load at crossfade_duration + 1 second buffer
      // - Gapless: Pre-load at 3 seconds remaining
      const preloadThreshold = crossfadeEnabled ? crossfadeDuration + 1 : 3;

      if (timeRemaining > 0 && timeRemaining <= preloadThreshold && nextAudioRef.current && !nextAudioRef.current.src) {
        console.log(`📥 Pre-loading next track for ${crossfadeEnabled ? 'crossfade' : 'gapless'} playback:`, nextTrack.title);

        const streamUrl = generateStreamUrl(nextTrack.id);
        nextAudioRef.current.src = streamUrl;
        nextAudioRef.current.load();
      }
    };

    // Check every 500ms during playback
    const intervalId = setInterval(checkPreload, 500);
    return () => clearInterval(intervalId);
  }, [nextTrack, enhancementSettings, gaplessEnabled, crossfadeEnabled, crossfadeDuration, generateStreamUrl]);

  /**
   * Perform crossfade effect
   */
  const performCrossfade = useCallback((currentAudio: HTMLAudioElement, nextAudio: HTMLAudioElement, duration: number) => {
    const startTime = Date.now();
    const targetVolume = (isMuted ? 0 : volume) / 100;
    const currentStartVolume = currentAudio.volume;

    const fade = () => {
      const elapsed = (Date.now() - startTime) / 1000; // seconds
      const progress = Math.min(elapsed / duration, 1); // 0 to 1

      // Ease-in-out curve for smoother transition
      const eased = progress < 0.5
        ? 2 * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 2) / 2;

      // Fade out current track
      currentAudio.volume = currentStartVolume * (1 - eased);

      // Fade in next track
      nextAudio.volume = targetVolume * eased;

      if (progress < 1) {
        requestAnimationFrame(fade);
      } else {
        // Crossfade complete
        console.log('✅ Crossfade complete');
        currentAudio.volume = 0;
        nextAudio.volume = targetVolume;
        currentAudio.pause();
        currentAudio.src = ''; // Clear the finished track

        // Swap audio element references for next cycle
        const tempSrc = audioRef.current?.src || '';
        const nextSrc = nextAudioRef.current?.src || '';

        if (audioRef.current) audioRef.current.src = nextSrc;
        if (nextAudioRef.current) nextAudioRef.current.src = tempSrc;

        // Notify parent of track switch
        if (onTrackSwitch) {
          onTrackSwitch();
        }
      }
    };

    requestAnimationFrame(fade);
  }, [volume, isMuted, audioRef, nextAudioRef, onTrackSwitch]);

  /**
   * Start crossfade at the right time
   */
  useEffect(() => {
    if (!crossfadeEnabled || !nextTrack || !audioRef.current || !nextAudioRef.current) {
      return;
    }

    const checkCrossfade = () => {
      if (!audioRef.current || !nextAudioRef.current) return;

      const timeRemaining = audioRef.current.duration - audioRef.current.currentTime;

      // Start crossfade when time remaining equals crossfade duration
      if (timeRemaining > 0 && timeRemaining <= crossfadeDuration) {
        // Only start if next track is loaded and not already playing
        if (nextAudioRef.current.src && nextAudioRef.current.paused) {
          console.log(`🎚️ Starting ${crossfadeDuration}s crossfade`);

          // Start playing the next track (it will fade in)
          nextAudioRef.current.volume = 0; // Start at 0 volume
          nextAudioRef.current.play().catch(err => {
            console.error('Failed to start crossfade:', err);
          });

          // Perform the crossfade
          performCrossfade(audioRef.current, nextAudioRef.current, crossfadeDuration);
        }
      }
    };

    // Check more frequently for smooth fade
    const intervalId = setInterval(checkCrossfade, 100);
    return () => clearInterval(intervalId);
  }, [crossfadeEnabled, crossfadeDuration, nextTrack, performCrossfade]);

  /**
   * Handle gapless transition (no crossfade)
   */
  useEffect(() => {
    if (!gaplessEnabled || crossfadeEnabled || !nextTrack || !audioRef.current || !nextAudioRef.current) {
      return;
    }

    const handleGaplessTransition = () => {
      if (!audioRef.current || !nextAudioRef.current) return;

      // When current track ends, switch to next track instantly
      console.log('🎵 Gapless transition to next track');

      // Play next track
      nextAudioRef.current.play().catch(err => {
        console.error('Failed to start gapless playback:', err);
      });

      // Swap audio elements
      const tempSrc = audioRef.current.src;
      const nextSrc = nextAudioRef.current.src;

      audioRef.current.src = nextSrc;
      nextAudioRef.current.src = '';

      // Notify parent
      if (onTrackSwitch) {
        onTrackSwitch();
      }
    };

    audioRef.current.addEventListener('ended', handleGaplessTransition);

    return () => {
      audioRef.current?.removeEventListener('ended', handleGaplessTransition);
    };
  }, [gaplessEnabled, crossfadeEnabled, nextTrack, onTrackSwitch]);

  /**
   * Sync volume with next audio element
   */
  useEffect(() => {
    if (nextAudioRef.current) {
      nextAudioRef.current.volume = (isMuted ? 0 : volume) / 100;
    }
  }, [volume, isMuted]);

  return {
    // State
    gaplessEnabled,
    crossfadeEnabled,
    crossfadeDuration,
    nextTrack,

    // Methods
    setGaplessEnabled,
    setCrossfadeEnabled,
    setCrossfadeDuration,
  };
}
