/**
 * useAudioVisualization Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides real-time audio analysis data for visual effects.
 * Uses Web Audio API's AnalyserNode to extract frequency and loudness data.
 *
 * Features:
 * - Bass, mid, treble frequency band extraction
 * - Overall loudness/energy detection
 * - Smoothed values for fluid animations
 * - Low CPU overhead via requestAnimationFrame
 *
 * Usage:
 *   const { bass, mid, treble, loudness, isActive } = useAudioVisualization();
 *   <StarfieldBackground audioReactivity={{ bass, mid, treble, loudness }} />
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSelector } from 'react-redux';
import { playerSelectors } from '@/store/selectors';

export interface AudioVisualizationData {
  /** Bass energy (20-250Hz), normalized 0-1 */
  bass: number;
  /** Mid energy (250-4000Hz), normalized 0-1 */
  mid: number;
  /** Treble energy (4000-20000Hz), normalized 0-1 */
  treble: number;
  /** Overall loudness/energy, normalized 0-1 */
  loudness: number;
  /** Peak detection (transient hits) */
  peak: number;
  /** Whether audio is currently active */
  isActive: boolean;
}

// Frequency band boundaries (in Hz)
const BASS_LOW = 20;
const BASS_HIGH = 250;
const MID_LOW = 250;
const MID_HIGH = 4000;
const TREBLE_LOW = 4000;
const TREBLE_HIGH = 20000;

// Smoothing factor (higher = smoother, slower response)
const SMOOTHING = 0.85;

// State update throttle: cap at ~30fps (one update per 33ms)
const MIN_UPDATE_INTERVAL_MS = 1000 / 30;

// Minimum per-channel delta to trigger a state update (skip noise)
const DELTA_THRESHOLD = 0.005;

// Default values when no audio
const DEFAULT_DATA: AudioVisualizationData = {
  bass: 0,
  mid: 0,
  treble: 0,
  loudness: 0,
  peak: 0,
  isActive: false,
};

/**
 * Get the global AudioContext used by the app
 * This connects to the same context used by AudioPlaybackEngine
 */
function getGlobalAudioContext(): AudioContext | null {
  // Check if there's a global audio context
  if (typeof window !== 'undefined' && (window as any).__auralisAudioContext) {
    return (window as any).__auralisAudioContext;
  }
  return null;
}

/**
 * Create or get a shared AnalyserNode
 */
function getOrCreateAnalyser(audioContext: AudioContext): AnalyserNode {
  // Check for existing analyser
  if ((window as any).__auralisAnalyser) {
    return (window as any).__auralisAnalyser;
  }

  // Create new analyser
  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;
  analyser.smoothingTimeConstant = 0.8;

  // Connect to destination (passthrough)
  // Note: The actual audio chain should connect through this analyser
  (window as any).__auralisAnalyser = analyser;

  return analyser;
}

/**
 * Calculate frequency band energy from FFT data
 */
function getBandEnergy(
  frequencyData: Uint8Array,
  sampleRate: number,
  _fftSize: number, // Kept for API consistency, not used directly
  lowFreq: number,
  highFreq: number
): number {
  const nyquist = sampleRate / 2;
  const binCount = frequencyData.length;
  const binWidth = nyquist / binCount;

  const lowBin = Math.floor(lowFreq / binWidth);
  const highBin = Math.min(Math.ceil(highFreq / binWidth), binCount - 1);

  let sum = 0;
  let count = 0;

  for (let i = lowBin; i <= highBin; i++) {
    // Convert from 0-255 to 0-1, with logarithmic weighting
    const value = frequencyData[i] / 255;
    sum += value * value; // Square for energy
    count++;
  }

  return count > 0 ? Math.sqrt(sum / count) : 0;
}

/**
 * Hook for real-time audio visualization data
 */
export function useAudioVisualization(enabled: boolean = true): AudioVisualizationData {
  const [data, setData] = useState<AudioVisualizationData>(DEFAULT_DATA);
  const isPlaying = useSelector(playerSelectors.selectIsPlaying);
  const streamingState = useSelector(playerSelectors.selectEnhancedStreamingState);

  // Audio is active when either regular playback or streaming is active
  const isAudioActive = isPlaying || streamingState === 'streaming';

  // Refs for animation frame and smoothed values
  const animationFrameRef = useRef<number | null>(null);
  const smoothedValuesRef = useRef({ bass: 0, mid: 0, treble: 0, loudness: 0, peak: 0 });
  const lastPeakRef = useRef(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const frequencyDataRef = useRef<Uint8Array | null>(null);

  // Throttle: timestamp of the last setData call
  const lastUpdateTimeRef = useRef(0);
  // Last values emitted to state — skip updates when delta is below threshold
  const lastEmittedRef = useRef({ bass: 0, mid: 0, treble: 0, loudness: 0, peak: 0 });

  // Initialize analyser when audio context becomes available
  useEffect(() => {
    if (!enabled || !isAudioActive) {
      setData(DEFAULT_DATA);
      return;
    }

    const audioContext = getGlobalAudioContext();
    if (!audioContext) {
      // No audio context yet - check periodically
      const checkInterval = setInterval(() => {
        const ctx = getGlobalAudioContext();
        if (ctx) {
          analyserRef.current = getOrCreateAnalyser(ctx);
          frequencyDataRef.current = new Uint8Array(analyserRef.current.frequencyBinCount);
          clearInterval(checkInterval);
        }
      }, 500);

      return () => clearInterval(checkInterval);
    }

    analyserRef.current = getOrCreateAnalyser(audioContext);
    frequencyDataRef.current = new Uint8Array(analyserRef.current.frequencyBinCount);
  }, [enabled, isAudioActive]);

  // Animation loop for reading audio data
  const updateVisualization = useCallback(() => {
    if (!analyserRef.current || !frequencyDataRef.current || !isAudioActive) {
      animationFrameRef.current = requestAnimationFrame(updateVisualization);
      return;
    }

    const analyser = analyserRef.current;
    const frequencyData = frequencyDataRef.current;
    const audioContext = getGlobalAudioContext();

    if (!audioContext) {
      animationFrameRef.current = requestAnimationFrame(updateVisualization);
      return;
    }

    // Get frequency data
    analyser.getByteFrequencyData(frequencyData);

    const sampleRate = audioContext.sampleRate;
    const fftSize = analyser.fftSize;

    // Calculate band energies
    const rawBass = getBandEnergy(frequencyData, sampleRate, fftSize, BASS_LOW, BASS_HIGH);
    const rawMid = getBandEnergy(frequencyData, sampleRate, fftSize, MID_LOW, MID_HIGH);
    const rawTreble = getBandEnergy(frequencyData, sampleRate, fftSize, TREBLE_LOW, TREBLE_HIGH);

    // Overall loudness (weighted average)
    const rawLoudness = rawBass * 0.4 + rawMid * 0.4 + rawTreble * 0.2;

    // Peak detection (sudden increases)
    const currentPeak = Math.max(rawBass, rawMid * 0.8);
    const peakDelta = currentPeak - lastPeakRef.current;
    const rawPeak = peakDelta > 0.1 ? Math.min(peakDelta * 3, 1) : 0;
    lastPeakRef.current = currentPeak;

    // Apply smoothing
    const smoothed = smoothedValuesRef.current;
    smoothed.bass = smoothed.bass * SMOOTHING + rawBass * (1 - SMOOTHING);
    smoothed.mid = smoothed.mid * SMOOTHING + rawMid * (1 - SMOOTHING);
    smoothed.treble = smoothed.treble * SMOOTHING + rawTreble * (1 - SMOOTHING);
    smoothed.loudness = smoothed.loudness * SMOOTHING + rawLoudness * (1 - SMOOTHING);
    smoothed.peak = smoothed.peak * 0.7 + rawPeak * 0.3; // Faster decay for peaks

    // Throttle state updates to ~30fps and skip if values haven't changed meaningfully
    const now = performance.now();
    if (now - lastUpdateTimeRef.current >= MIN_UPDATE_INTERVAL_MS) {
      const last = lastEmittedRef.current;
      const maxDelta = Math.max(
        Math.abs(smoothed.bass - last.bass),
        Math.abs(smoothed.mid - last.mid),
        Math.abs(smoothed.treble - last.treble),
        Math.abs(smoothed.loudness - last.loudness),
        Math.abs(smoothed.peak - last.peak),
      );
      if (maxDelta >= DELTA_THRESHOLD) {
        lastUpdateTimeRef.current = now;
        last.bass = smoothed.bass;
        last.mid = smoothed.mid;
        last.treble = smoothed.treble;
        last.loudness = smoothed.loudness;
        last.peak = smoothed.peak;
        setData({
          bass: smoothed.bass,
          mid: smoothed.mid,
          treble: smoothed.treble,
          loudness: smoothed.loudness,
          peak: smoothed.peak,
          isActive: true,
        });
      }
    }

    animationFrameRef.current = requestAnimationFrame(updateVisualization);
  }, [isAudioActive]);

  // Start/stop animation loop
  useEffect(() => {
    if (!enabled) {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      setData(DEFAULT_DATA);
      return;
    }

    if (isAudioActive) {
      animationFrameRef.current = requestAnimationFrame(updateVisualization);
    } else {
      // Decay values when stopped
      const decay = () => {
        const smoothed = smoothedValuesRef.current;
        smoothed.bass *= 0.95;
        smoothed.mid *= 0.95;
        smoothed.treble *= 0.95;
        smoothed.loudness *= 0.95;
        smoothed.peak *= 0.9;

        if (smoothed.loudness > 0.01) {
          setData({
            bass: smoothed.bass,
            mid: smoothed.mid,
            treble: smoothed.treble,
            loudness: smoothed.loudness,
            peak: smoothed.peak,
            isActive: false,
          });
          animationFrameRef.current = requestAnimationFrame(decay);
        } else {
          setData(DEFAULT_DATA);
        }
      };
      animationFrameRef.current = requestAnimationFrame(decay);
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [enabled, isAudioActive, updateVisualization]);

  return data;
}

/**
 * Register an AudioContext for visualization
 * Call this when creating the main audio context
 */
export function registerAudioContext(audioContext: AudioContext): void {
  (window as any).__auralisAudioContext = audioContext;
}

/**
 * Connect an audio node to the visualization analyser
 * Call this to insert the analyser into the audio chain
 */
export function connectToVisualizer(sourceNode: AudioNode, destinationNode: AudioNode): void {
  const audioContext = sourceNode.context as AudioContext;
  const analyser = getOrCreateAnalyser(audioContext);

  // Insert analyser between source and destination
  sourceNode.connect(analyser);
  analyser.connect(destinationNode);
}

export default useAudioVisualization;
