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

import React from 'react';
import { useAudioPolicyBridge } from './useAudioPolicyBridge';

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
  debug = false,
}) => {
  const { audioRef } = useAudioPolicyBridge({ onAudioContextEnabled, debug });

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
