/**
 * Audio visualization store + sampler
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Module-level mutable store for analyser data, written by
 * sampleAudioVisualization() and read by StarfieldBackground's render loop
 * straight off the object — no React state in the path (#5664: pushing these
 * values through setState re-rendered the background ~30x/s for a consumer
 * that only read them from a ref).
 *
 * The sampler is deliberately React-free so the starfield's own rAF loop can
 * drive it (#5661): one loop samples the analyser and draws, instead of two
 * loops racing at display refresh rate.
 */

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

export function makeDefaultVisualizationData(): AudioVisualizationData {
  return { bass: 0, mid: 0, treble: 0, loudness: 0, peak: 0, isActive: false };
}

/** The live values. Mutated in place; read `getAudioVisualization()` */
const data = makeDefaultVisualizationData();

/**
 * Listeners notified when isActive flips. The starfield uses this to
 * restart its (cancelled) render loop when playback resumes — everything
 * else about the data changes silently, because only the loop that polls
 * the store can see those.
 */
const isActiveListeners = new Set<() => void>();

export function getAudioVisualization(): AudioVisualizationData {
  return data;
}

export function subscribeToIsActive(listener: () => void): () => void {
  isActiveListeners.add(listener);
  return () => {
    isActiveListeners.delete(listener);
  };
}

function setActive(isActive: boolean): void {
  if (data.isActive === isActive) return;
  data.isActive = isActive;
  for (const listener of [...isActiveListeners]) listener();
}

export function resetAudioVisualization(): void {
  Object.assign(data, makeDefaultVisualizationData());
  setActive(false);
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

// Sampling cap: ~30Hz is plenty for eased visuals and halves the sampler's
// work at display refresh rates (#5661).
const MIN_SAMPLE_INTERVAL_MS = 1000 / 30;

// Per-frame decay applied while audio is inactive, until values settle
const DECAY_FACTOR = 0.95;
const PEAK_DECAY_FACTOR = 0.9;
const SETTLED_LOUDNESS = 0.01;

const smoothed = { bass: 0, mid: 0, treble: 0, loudness: 0, peak: 0 };
const lastPeak = { value: 0 };
let lastSampleTime = -Infinity;
// Reused FFT scratch buffer — allocating per sample would churn the GC 30x/s.
let frequencyData: Uint8Array<ArrayBuffer> | null = null;

/**
 * Calculate frequency band energy from FFT data
 */
function getBandEnergy(
  frequencyData: Uint8Array,
  sampleRate: number,
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

/** Whether the audio chain is currently delivering signal. */
let audioActive = false;

export function setAudioVisualizationActive(active: boolean): void {
  audioActive = active;
}

/**
 * Advance the visualization one tick: sample the analyser (throttled to
 * ~30Hz), smooth into the store — or decay toward zero while inactive.
 *
 * Returns true when the visualization is fully settled and inactive, i.e.
 * the driving render loop may stop after one final static frame (#5661).
 */
export function sampleAudioVisualization(now: number): boolean {
  const analyser = window.__auralisAnalyser;
  const audioContext = window.__auralisAudioContext;

  if (!audioActive || !analyser || !audioContext) {
    // Fade whatever is on screen out gracefully before declaring settled.
    smoothed.bass *= DECAY_FACTOR;
    smoothed.mid *= DECAY_FACTOR;
    smoothed.treble *= DECAY_FACTOR;
    smoothed.loudness *= DECAY_FACTOR;
    smoothed.peak *= PEAK_DECAY_FACTOR;

    data.bass = smoothed.bass;
    data.mid = smoothed.mid;
    data.treble = smoothed.treble;
    data.loudness = smoothed.loudness;
    data.peak = smoothed.peak;

    if (smoothed.loudness <= SETTLED_LOUDNESS) {
      Object.assign(data, makeDefaultVisualizationData(), { isActive: false });
      Object.assign(smoothed, { bass: 0, mid: 0, treble: 0, loudness: 0, peak: 0 });
      setActive(false);
      return true;
    }
    setActive(false);
    return false;
  }

  if (now - lastSampleTime < MIN_SAMPLE_INTERVAL_MS) {
    return false;
  }
  lastSampleTime = now;

  if (!frequencyData || frequencyData.length !== analyser.frequencyBinCount) {
    frequencyData = new Uint8Array(new ArrayBuffer(analyser.frequencyBinCount));
  }
  analyser.getByteFrequencyData(frequencyData);

  const rawBass = getBandEnergy(frequencyData, audioContext.sampleRate, BASS_LOW, BASS_HIGH);
  const rawMid = getBandEnergy(frequencyData, audioContext.sampleRate, MID_LOW, MID_HIGH);
  const rawTreble = getBandEnergy(frequencyData, audioContext.sampleRate, TREBLE_LOW, TREBLE_HIGH);

  // Overall loudness (weighted average)
  const rawLoudness = rawBass * 0.4 + rawMid * 0.4 + rawTreble * 0.2;

  // Peak detection (sudden increases)
  const currentPeak = Math.max(rawBass, rawMid * 0.8);
  const peakDelta = currentPeak - lastPeak.value;
  const rawPeak = peakDelta > 0.1 ? Math.min(peakDelta * 3, 1) : 0;
  lastPeak.value = currentPeak;

  smoothed.bass = smoothed.bass * SMOOTHING + rawBass * (1 - SMOOTHING);
  smoothed.mid = smoothed.mid * SMOOTHING + rawMid * (1 - SMOOTHING);
  smoothed.treble = smoothed.treble * SMOOTHING + rawTreble * (1 - SMOOTHING);
  smoothed.loudness = smoothed.loudness * SMOOTHING + rawLoudness * (1 - SMOOTHING);
  smoothed.peak = smoothed.peak * 0.7 + rawPeak * 0.3; // Faster decay for peaks

  data.bass = smoothed.bass;
  data.mid = smoothed.mid;
  data.treble = smoothed.treble;
  data.loudness = smoothed.loudness;
  data.peak = smoothed.peak;
  setActive(true);
  return false;
}

/**
 * Get the global AudioContext used by the app.
 * This connects to the same context used by AudioPlaybackEngine.
 */
export function getGlobalAudioContext(): AudioContext | null {
  if (typeof window !== 'undefined' && window.__auralisAudioContext) {
    return window.__auralisAudioContext;
  }
  return null;
}

/**
 * Create or get a shared AnalyserNode.
 */
export function getOrCreateAnalyser(audioContext: AudioContext): AnalyserNode {
  if (window.__auralisAnalyser) {
    return window.__auralisAnalyser;
  }

  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;
  analyser.smoothingTimeConstant = 0.8;

  // Connect to destination (passthrough)
  // Note: The actual audio chain should connect through this analyser
  window.__auralisAnalyser = analyser;

  return analyser;
}

/** Test hook: reset all module state between tests. */
export function resetAudioVisualizationModuleForTests(): void {
  resetAudioVisualization();
  Object.assign(smoothed, { bass: 0, mid: 0, treble: 0, loudness: 0, peak: 0 });
  lastPeak.value = 0;
  lastSampleTime = -Infinity;
  audioActive = false;
  isActiveListeners.clear();
}

/**
 * Register an AudioContext for visualization.
 * Call this when creating the main audio context.
 */
export function registerAudioContext(audioContext: AudioContext): void {
  window.__auralisAudioContext = audioContext;
}

/**
 * Connect an audio node to the visualization analyser.
 * Call this to insert the analyser into the audio chain.
 */
export function connectToVisualizer(sourceNode: AudioNode, destinationNode: AudioNode): void {
  const audioContext = sourceNode.context as AudioContext;
  const analyser = getOrCreateAnalyser(audioContext);

  // Insert analyser between source and destination
  sourceNode.connect(analyser);
  analyser.connect(destinationNode);
}
