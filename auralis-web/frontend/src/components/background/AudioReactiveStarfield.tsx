/**
 * AudioReactiveStarfield
 *
 * Hosts the audio-visualization wiring (analyser + active flag) next to the
 * starfield that renders it. Since #5664 the values themselves travel through
 * the mutable visualization store — the starfield reads them in its own rAF
 * loop — so this wrapper passes no data props any more.
 *
 * @component
 */

import { StarfieldBackground } from './StarfieldBackground';
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

export const AudioReactiveStarfield = ({
  enableParallax = true,
  parallaxStrength = 0.5,
  speed = 1.0,
  zIndex = -1,
  className,
  enableAudioReactivity = true,
}: AudioReactiveStarfieldProps) => {
  // Wire playback state to the visualization store; the starfield's render
  // loop consumes it.
  useAudioVisualization(enableAudioReactivity);

  return (
    <StarfieldBackground
      enableParallax={enableParallax}
      parallaxStrength={parallaxStrength}
      speed={speed}
      zIndex={zIndex}
      className={className}
    />
  );
};

export default AudioReactiveStarfield;
