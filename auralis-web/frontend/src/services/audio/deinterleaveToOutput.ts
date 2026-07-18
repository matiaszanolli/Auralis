/**
 * deinterleaveToOutput - copy interleaved PCM samples into Web Audio output channels
 *
 * Pure function extracted from BufferScheduler.handleAudioProcess (#4301) —
 * no Web Audio API dependency beyond the minimal output shape, so it is
 * trivially unit-testable without mocking an AudioContext.
 */

export interface ChannelWritableOutput {
  numberOfChannels: number;
  getChannelData: (channel: number) => Float32Array;
}

/**
 * Copy `framesNeeded` frames of interleaved `samples` (sourceChannels per
 * frame) into `output`'s channels, de-interleaving as needed. Pads any
 * shortfall with silence.
 */
export function deinterleaveToOutput(
  output: ChannelWritableOutput,
  samples: Float32Array,
  framesNeeded: number,
  sourceChannels: number
): void {
  const channelCount = output.numberOfChannels;

  if (sourceChannels === 1) {
    // Mono source - copy to all output channels
    const monoData = samples.subarray(0, framesNeeded);
    for (let ch = 0; ch < channelCount; ch++) {
      output.getChannelData(ch).set(monoData);
    }
  } else if (sourceChannels === 2) {
    // Stereo source - de-interleave samples
    const left = output.getChannelData(0);
    const right = output.getChannelData(1);
    const framesToProcess = Math.min(framesNeeded, Math.floor(samples.length / 2));

    for (let i = 0; i < framesToProcess; i++) {
      left[i] = samples[i * 2] || 0;
      right[i] = samples[i * 2 + 1] || 0;
    }

    // Fill remaining with silence if we didn't get enough samples
    for (let i = framesToProcess; i < framesNeeded; i++) {
      left[i] = 0;
      right[i] = 0;
    }
  } else {
    // Multichannel - distribute samples across channels
    for (let ch = 0; ch < channelCount; ch++) {
      const channelData = output.getChannelData(ch);
      for (let i = 0; i < framesNeeded; i++) {
        const sampleIndex = i * sourceChannels + ch;
        if (sampleIndex < samples.length) {
          channelData[i] = samples[sampleIndex];
        } else {
          channelData[i] = 0;
        }
      }
    }
  }
}

export default deinterleaveToOutput;
