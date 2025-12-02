/**
 * HiddenAudioElement - Browser Policy Compliance & Actual Audio Playback
 * ========================================================================
 *
 * This component provides a hidden HTML5 audio element that:
 * 1. Satisfies browser autoplay policies requiring user gesture
 * 2. Actually streams audio from /api/player/stream/{track_id}
 * 3. Syncs with player state via WebSocket
 *
 * Audio Flow:
 * - Player component loads track via usePlayerAPI.playTrack()
 * - Backend sets current track in player state
 * - This element receives track ID via Redux or PlayerAPI
 * - Audio element src becomes /api/player/stream/{track_id}
 * - Browser policy: User click on play button → play() called → audio starts
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import React, { useEffect, useRef, useState } from 'react';
import { useAudioPolicyBridge } from './useAudioPolicyBridge';
import { usePlayerAPI } from '../../hooks/usePlayerAPI';

interface HiddenAudioElementProps {
  /** Called when audio context should be enabled (user gesture received) */
  onAudioContextEnabled?: () => void;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * HiddenAudioElement Component
 *
 * Actually streams audio from the backend player API.
 * Updates src when current track changes.
 */
export const HiddenAudioElement: React.FC<HiddenAudioElementProps> = ({
  onAudioContextEnabled,
  debug = false,
}) => {
  const { audioRef } = useAudioPolicyBridge({ onAudioContextEnabled, debug });
  const { currentTrack } = usePlayerAPI();
  const [audioSrc, setAudioSrc] = useState<string>('');

  // Handle audio load errors
  useEffect(() => {
    if (!audioRef.current) return;

    const handleError = (e: Event) => {
      const audio = audioRef.current as HTMLAudioElement;
      const error = audio.error;
      let errorMsg = 'Unknown error';

      if (error) {
        switch (error.code) {
          case 1: errorMsg = 'Audio loading aborted'; break;
          case 2: errorMsg = 'Network error loading audio'; break;
          case 3: errorMsg = 'Audio decoding failed'; break;
          case 4: errorMsg = 'Audio format not supported'; break;
          default: errorMsg = `Audio error: ${error.code}`;
        }
      }

      console.error(`[HiddenAudioElement] ${errorMsg}`, audio.src);
    };

    const handleCanPlay = () => {
      console.log(`[HiddenAudioElement] Audio loaded and ready to play`);
    };

    const handlePlay = () => {
      console.log(`[HiddenAudioElement] Audio playback started`);
    };

    audioRef.current.addEventListener('error', handleError);
    audioRef.current.addEventListener('canplay', handleCanPlay);
    audioRef.current.addEventListener('play', handlePlay);

    return () => {
      audioRef.current?.removeEventListener('error', handleError);
      audioRef.current?.removeEventListener('canplay', handleCanPlay);
      audioRef.current?.removeEventListener('play', handlePlay);
    };
  }, [audioRef]);

  // Update audio element src when current track changes
  useEffect(() => {
    if (!audioRef.current) {
      console.warn('[HiddenAudioElement] Audio element not available');
      return;
    }

    if (currentTrack?.id) {
      const streamUrl = `/api/player/stream/${currentTrack.id}`;

      console.log(
        `[HiddenAudioElement] Loading track: "${currentTrack.title}" from ${streamUrl}`
      );

      // Set the audio source
      audioRef.current.src = streamUrl;
      setAudioSrc(streamUrl);

      // Trigger loading
      audioRef.current.load();
    } else {
      // Clear source if no track
      console.log('[HiddenAudioElement] No track to load, clearing source');
      audioRef.current.src = '';
      setAudioSrc('');
    }
  }, [currentTrack?.id, currentTrack?.title, audioRef]);

  return (
    <>
      {/* Hidden audio element for actual audio streaming */}
      {/* - Visible: display: none (hidden from UI) */}
      {/* - Playable: HTML5 audio element with stream URL */}
      {/* - Browser policy: satisfies autoplay requirement via user gesture */}
      <audio
        ref={audioRef}
        style={{ display: 'none' }}
        crossOrigin="anonymous"
        controls={false}
        preload="auto"
      />
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
