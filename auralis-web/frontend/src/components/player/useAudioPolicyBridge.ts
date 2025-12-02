/**
 * useAudioPolicyBridge - Hook for browser autoplay policy compliance
 *
 * Manages audio element lifecycle and play gesture handling.
 * Satisfies browser requirement for user gesture before audio playback.
 */

import { useRef, useEffect } from 'react';

interface UseAudioPolicyBridgeProps {
  onAudioContextEnabled?: () => void;
  debug?: boolean;
}

export const useAudioPolicyBridge = ({
  onAudioContextEnabled,
  debug = false,
}: UseAudioPolicyBridgeProps) => {
  const audioRef = useRef<HTMLAudioElement>(null);

  const log = (msg: string) => {
    if (debug) {
      console.log(`[AudioPolicyBridge] ${msg}`);
    }
  };

  /**
   * Initialize audio element and handle user gestures
   */
  useEffect(() => {
    const audioElement = audioRef.current;
    if (!audioElement) return;

    // Set up CORS for potential remote streaming
    audioElement.crossOrigin = 'anonymous';

    // Configure for actual audio playback (NOT silent)
    // - muted: false (MUST be false to hear audio)
    // - playsInline: true (for mobile inline playback)
    // - preload: 'auto' (allow browser to preload audio data)
    audioElement.muted = false;
    (audioElement as any).playsInline = true;
    audioElement.preload = 'auto';

    log('Audio element configured');

    // Handle play attempt (satisfies browser autoplay policy)
    const handlePlay = async () => {
      log('Play gesture detected - audio context may now play');
      if (onAudioContextEnabled) {
        onAudioContextEnabled();
      }
    };

    // Handle pause (cleanup)
    const handlePause = () => {
      log('Audio paused');
    };

    audioElement.addEventListener('play', handlePlay);
    audioElement.addEventListener('pause', handlePause);

    return () => {
      audioElement.removeEventListener('play', handlePlay);
      audioElement.removeEventListener('pause', handlePause);
    };
  }, [onAudioContextEnabled, debug]);

  /**
   * Trigger play (this satisfies browser autoplay policy)
   * Call this from user gesture handlers (click, etc.)
   *
   * IMPORTANT: We do NOT pause immediately - audio should continue playing
   * The gesture is just to satisfy browser autoplay policy
   */
  const triggerPlay = () => {
    if (audioRef.current) {
      log('Triggering play gesture...');
      const playPromise = audioRef.current.play();

      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            log('Play gesture accepted - audio will play');
            // DO NOT pause - let audio continue playing
          })
          .catch((err: any) => {
            log(`Play gesture rejected: ${err.message}`);
          });
      }
    }
  };

  /**
   * Expose trigger method globally after hook mounts
   */
  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).__auralisAudioElementTriggerPlay = triggerPlay;
      log('Audio play gesture trigger registered globally');

      return () => {
        // Cleanup if component unmounts
        delete (window as any).__auralisAudioElementTriggerPlay;
      };
    }
  }, []);

  return { audioRef };
};
