/**
 * useAudioVisualization Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Wires playback state and the shared AnalyserNode to the audio
 * visualization store (audioVisualization.ts). Runs no loop of its own:
 * sampleAudioVisualization() is driven by StarfieldBackground's render loop
 * (#5661), and results travel through the mutable store instead of React
 * state (#5664 — state updates here re-rendered the background ~30x/s for a
 * consumer that read the values from a ref anyway).
 *
 * Usage:
 *   useAudioVisualization();          // anywhere under the providers
 *   getAudioVisualization()           // read the live values
 */

import { useEffect } from 'react';
import { useSelector } from 'react-redux';
import { playerSelectors } from '@/store/selectors';
import {
  getAudioVisualization,
  getGlobalAudioContext,
  getOrCreateAnalyser,
  setAudioVisualizationActive,
} from './audioVisualization';

export type { AudioVisualizationData } from './audioVisualization';
export {
  registerAudioContext,
  connectToVisualizer,
} from './audioVisualization';

/**
 * Hook that keeps the visualization store fed while audio is active.
 *
 * Returns the live store object (a stable reference — reading it in render
 * will not subscribe you to anything; the starfield consumes it inside its
 * rAF loop).
 */
export function useAudioVisualization(enabled: boolean = true): ReturnType<typeof getAudioVisualization> {
  const isPlaying = useSelector(playerSelectors.selectIsPlaying);
  const streamingState = useSelector(playerSelectors.selectEnhancedStreamingState);

  // Audio is active when either regular playback or streaming is active.
  // 'complete' means delivery finished, not playback: the buffered tail keeps
  // playing (and feeding the analyser) until the track ends (#5603).
  const isAudioActive =
    enabled && (isPlaying || streamingState === 'streaming' || streamingState === 'complete');

  // Flag the sampler and make sure an analyser exists. When no context has
  // been registered yet, poll briefly (#4481) instead of scheduling a frame
  // loop that would spin without producing anything.
  useEffect(() => {
    setAudioVisualizationActive(isAudioActive);

    if (!isAudioActive) return;

    const audioContext = getGlobalAudioContext();
    if (!audioContext) {
      const checkInterval = setInterval(() => {
        const ctx = getGlobalAudioContext();
        if (ctx) {
          getOrCreateAnalyser(ctx);
          clearInterval(checkInterval);
        }
      }, 500);

      return () => clearInterval(checkInterval);
    }

    getOrCreateAnalyser(audioContext);
  }, [isAudioActive]);

  return getAudioVisualization();
}

export default useAudioVisualization;
