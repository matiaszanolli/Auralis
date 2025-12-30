/**
 * AudioReactiveStarfield
 *
 * Wrapper component that connects the audio visualization hook to StarfieldBackground.
 * When music is playing, the starfield reacts to:
 * - Bass (20-250Hz): Nebula pulse/glow
 * - Mid (250-4000Hz): Aurora intensity
 * - Treble (4000-20000Hz): Star sparkle/twinkle
 * - Loudness: Overall brightness and forward drift
 * - Peak: Flash effect on transients/beats
 *
 * @component
 */

import React from 'react';
import { StarfieldBackground } from './StarfieldBackground';
import type { AudioReactivityData } from './StarfieldBackground';
import { useAudioVisualization } from '@/hooks/audio/useAudioVisualization';

interface AudioReactiveStarfieldProps {
  /** Enable parallax effect on mouse movement (default: true) */
  enableParallax?: boolean;
  /** Parallax strength 0-1 (default: 0.5) */
  parallaxStrength?: number;
  /** Animation speed multiplier (default: 1.0) */
  speed?: number;
  /** CSS z-index (default: -1) */
  zIndex?: number;
  /** Additional CSS class */
  className?: string;
  /** Enable audio reactivity (default: true) */
  enableAudioReactivity?: boolean;
}

export const AudioReactiveStarfield: React.FC<AudioReactiveStarfieldProps> = ({
  enableParallax = true,
  parallaxStrength = 0.5,
  speed = 1.0,
  zIndex = -1,
  className,
  enableAudioReactivity = true,
}) => {
  // Get real-time audio analysis data from Web Audio API
  const audioData = useAudioVisualization(enableAudioReactivity);

  // Convert hook data to starfield's expected format
  const audioReactivity: AudioReactivityData = {
    bass: audioData.bass,
    mid: audioData.mid,
    treble: audioData.treble,
    loudness: audioData.loudness,
    peak: audioData.peak,
    isActive: audioData.isActive,
  };

  return (
    <StarfieldBackground
      enableParallax={enableParallax}
      parallaxStrength={parallaxStrength}
      speed={speed}
      zIndex={zIndex}
      className={className}
      audioReactivity={audioReactivity}
    />
  );
};

export default AudioReactiveStarfield;
