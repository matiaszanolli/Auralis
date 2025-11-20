/**
 * HiddenAudioElement - Browser Policy Compliance & Audio Output
 * ============================================================
 *
 * This component provides a hidden HTML5 audio element that:
 * 1. Satisfies browser autoplay policies requiring user gesture
 * 2. Creates an audio context that can be used for playback
 * 3. Provides reference for potential MSE (Media Source Extensions) fallback
 *
 * IMPORTANT: This is NOT a traditional audio player. Instead:
 * - Audio playback happens through Web Audio API (AudioContext)
 * - This component ensures browser policies are met
 * - The audio element serves as a policy bridge
 *
 * Browser Autoplay Policy:
 * - Chrome/Firefox: Require user gesture (click) before playing audio
 * - This component helps satisfy that requirement
 * - User clicks Play button → triggers this element → enables AudioContext
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import React, { useRef, useEffect } from 'react';

interface HiddenAudioElementProps {
  /** Called when audio context should be enabled (user gesture received) */
  onAudioContextEnabled?: () => void;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * HiddenAudioElement Component
 *
 * Creates a hidden audio element that helps with browser autoplay policies.
 * The actual playback happens through Web Audio API, not through this element.
 */
export const HiddenAudioElement: React.FC<HiddenAudioElementProps> = ({
  onAudioContextEnabled,
  debug = false
}) => {
  const audioRef = useRef<HTMLAudioElement>(null);

  const log = (msg: string) => {
    if (debug) {
      console.log(`[HiddenAudioElement] ${msg}`);
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

    // Configure for silent operation (used for policy only)
    audioElement.muted = true;
    audioElement.playsInline = true;
    audioElement.preload = 'none';

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
   */
  const triggerPlay = () => {
    if (audioRef.current) {
      log('Triggering play gesture...');
      const playPromise = audioRef.current.play();

      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            log('Play gesture accepted');
            // Immediately pause - we don't actually play audio here
            audioRef.current?.pause();
          })
          .catch((err: any) => {
            log(`Play gesture rejected: ${err.message}`);
          });
      }
    }
  };

  return (
    <>
      {/* Hidden audio element for browser policy compliance */}
      {/* This element is NOT used for actual playback - that's Web Audio API */}
      {/* It serves only to satisfy browser autoplay policies */}
      <audio
        ref={audioRef}
        style={{ display: 'none' }}
        crossOrigin="anonymous"
        controls={false}
      />

      {/* Expose trigger method through context or direct call */}
      {typeof window !== 'undefined' &&
        (() => {
          // Store trigger function on window for access from hooks
          (window as any).__auralisAudioElementTriggerPlay = triggerPlay;
          return null;
        })()}
    </>
  );
};

/**
 * Utility function to trigger audio play gesture from anywhere
 * Use this in play button handlers to satisfy browser policies
 */
export const triggerAudioPlayGesture = () => {
  const trigger = (window as any).__auralisAudioElementTriggerPlay;
  if (typeof trigger === 'function') {
    trigger();
  } else {
    console.warn('[HiddenAudioElement] Play gesture trigger not available - ensure HiddenAudioElement is mounted');
  }
};

export default HiddenAudioElement;
