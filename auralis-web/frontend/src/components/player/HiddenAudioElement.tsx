/**
 * HiddenAudioElement - Browser Policy Compliance & Actual Audio Playback
 * ========================================================================
 *
 * This component provides a hidden HTML5 audio element that:
 * 1. Satisfies browser autoplay policies requiring user gesture
 * 2. Actually streams audio from /api/player/stream/{track_id}
 * 3. Syncs with player state via WebSocket
 *
 * Architecture:
 * - Fetches authoritative current track from /api/player/status on mount
 * - Listens to WebSocket player_state messages for track changes
 * - Sets audio element src = /api/player/stream/{track_id}
 * - Ensures src is always set before play() is called
 *
 * Why Direct API Fetch?
 * - usePlayerAPI hook state might be stale on startup
 * - Backend /api/player/status is authoritative source
 * - Prevents race condition where play() called before src set
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useAudioPolicyBridge } from './useAudioPolicyBridge';
import { useWebSocketContext } from '../../contexts/WebSocketContext';
import { useEnhancement } from '../../contexts/EnhancementContext';

interface HiddenAudioElementProps {
  /** Called when audio context should be enabled (user gesture received) */
  onAudioContextEnabled?: () => void;
  /** Enable debug logging */
  debug?: boolean;
}

interface TrackInfo {
  id: number;
  title: string;
  artist: string;
  duration: number;
}

/**
 * HiddenAudioElement Component
 *
 * Manages HTML5 audio element and streams from backend.
 * Ensures audio src is set before playback attempts.
 */
export const HiddenAudioElement: React.FC<HiddenAudioElementProps> = ({
  onAudioContextEnabled,
  debug = false,
}) => {
  const { audioRef } = useAudioPolicyBridge({ onAudioContextEnabled, debug });
  const { subscribe } = useWebSocketContext();
  const { settings: enhancementSettings } = useEnhancement();
  const [currentTrack, setCurrentTrack] = useState<TrackInfo | null>(null);
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

  // Fetch current track from backend on mount
  // This ensures we have the authoritative state, not a stale hook state
  useEffect(() => {
    const fetchCurrentTrack = async () => {
      try {
        const response = await fetch('/api/player/status');
        if (response.ok) {
          const state = await response.json();
          if (state.current_track?.id) {
            setCurrentTrack(state.current_track);
            if (debug) {
              console.log(
                `[HiddenAudioElement] Fetched current track on mount: "${state.current_track.title}"`
              );
            }
          }
        }
      } catch (err) {
        console.error('[HiddenAudioElement] Failed to fetch current track:', err);
      }
    };

    fetchCurrentTrack();
  }, [debug]);

  // Listen to WebSocket for track changes
  // This keeps audio element in sync as user plays different tracks
  useEffect(() => {
    if (!subscribe) return;

    const unsubscribe = subscribe('player_state', (message: any) => {
      try {
        const state = message.data;
        if (state.current_track?.id) {
          setCurrentTrack(state.current_track);
          if (debug) {
            console.log(
              `[HiddenAudioElement] WebSocket: Track changed to "${state.current_track.title}"`
            );
          }
        }
      } catch (err) {
        console.error('[HiddenAudioElement] Error processing player_state:', err);
      }
    });

    return () => unsubscribe?.();
  }, [subscribe, debug]);

  // Update audio element src when current track changes
  // This is the ONLY place where we modify audio.src
  // Includes enhancement parameters if enhancement is enabled
  useEffect(() => {
    if (!audioRef.current) {
      console.warn('[HiddenAudioElement] Audio element not available');
      return;
    }

    if (currentTrack?.id) {
      // Build stream URL with enhancement parameters if enabled
      const baseUrl = `/api/player/stream/${currentTrack.id}`;
      let streamUrl = baseUrl;

      if (enhancementSettings.enabled) {
        const params = new URLSearchParams({
          enhanced: 'true',
          preset: enhancementSettings.preset,
          intensity: enhancementSettings.intensity.toString(),
        });
        streamUrl = `${baseUrl}?${params.toString()}`;
      }

      if (debug) {
        console.log(
          `[HiddenAudioElement] Setting audio src: "${currentTrack.title}" → ${streamUrl}${enhancementSettings.enabled ? ' (enhanced)' : ' (raw)'}`
        );
      }

      // Set the audio source
      audioRef.current.src = streamUrl;
      setAudioSrc(streamUrl);

      // Trigger loading - this initiates the HTTP request for audio
      audioRef.current.load();
    } else {
      // Clear source if no track
      if (debug) {
        console.log('[HiddenAudioElement] No track, clearing audio src');
      }
      audioRef.current.src = '';
      setAudioSrc('');
    }
  }, [currentTrack?.id, currentTrack?.title, enhancementSettings.enabled, enhancementSettings.preset, enhancementSettings.intensity, audioRef, debug]);

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
