import { useState, useEffect, useRef } from 'react';

const DECAY_DURATION_MS = 2500; // 2.5 seconds of graceful fade

export interface PlaybackDecayState {
  /** True when playing OR during decay period */
  isAnimating: boolean;
  /** 1.0 = full intensity, fades to 0 during decay */
  intensity: number;
  /** True only when actually playing (not during decay) */
  isPlaying: boolean;
}

/**
 * Custom hook that provides graceful animation decay when playback stops.
 * Instead of instantly freezing, animations fade over 2-3 seconds.
 * Glow effects fade last, creating a "lingering impression" effect.
 */
export function usePlaybackWithDecay(isPlaying: boolean): PlaybackDecayState {
  const [isAnimating, setIsAnimating] = useState(isPlaying);
  const [intensity, setIntensity] = useState(isPlaying ? 1 : 0);
  const wasPlayingRef = useRef(isPlaying);
  const decayStartTimeRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  // Track mounted state to guard against post-unmount setState calls (#2338)
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    // Transition: stopped → playing
    if (isPlaying && !wasPlayingRef.current) {
      // Cancel any decay in progress
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      decayStartTimeRef.current = null;
      setIsAnimating(true);
      setIntensity(1);
    }

    // Transition: playing → stopped (start decay)
    if (!isPlaying && wasPlayingRef.current) {
      decayStartTimeRef.current = performance.now();

      const animateDecay = (currentTime: number) => {
        // Guard: stop if component unmounted or decay was reset
        if (!mountedRef.current || !decayStartTimeRef.current) return;

        const elapsed = currentTime - decayStartTimeRef.current;
        const progress = Math.min(elapsed / DECAY_DURATION_MS, 1);

        // Easing: slow start, faster end (impression lingers longer)
        // Using quintic ease-out reversed for slow fade
        const easedProgress = 1 - Math.pow(1 - progress, 3);
        const newIntensity = 1 - easedProgress;

        setIntensity(newIntensity);

        if (progress < 1) {
          animationFrameRef.current = requestAnimationFrame(animateDecay);
        } else {
          // Decay complete
          animationFrameRef.current = null;
          decayStartTimeRef.current = null;
          setIsAnimating(false);
          setIntensity(0);
        }
      };

      animationFrameRef.current = requestAnimationFrame(animateDecay);
    }

    wasPlayingRef.current = isPlaying;

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [isPlaying]);

  return { isAnimating, intensity, isPlaying };
}
