/**
 * AudioWorkletProcessor for Auralis playback engine (#2347)
 *
 * Replaces deprecated ScriptProcessorNode with AudioWorklet.
 * Runs on the audio rendering thread (not main thread) for better performance.
 *
 * Communication protocol:
 * - Main thread sends PCM samples via port.postMessage({ samples: Float32Array })
 * - Main thread sends control messages: { command: 'stop' | 'setVolume', ... }
 * - Processor sends state updates: { type: 'underrun' | 'samplesPlayed', ... }
 */

class AuralisPlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    /** @type {Float32Array[]} Ring of sample buffers */
    this._buffers = [];
    /** Total samples available across all buffers */
    this._available = 0;
    /** Read offset in current buffer */
    this._readOffset = 0;
    /** Total samples rendered */
    this._samplesPlayed = 0;
    /** Whether to output audio */
    this._active = true;

    this.port.onmessage = (event) => {
      const { data } = event;
      if (data.samples) {
        // Receive interleaved PCM samples from main thread
        this._buffers.push(new Float32Array(data.samples));
        this._available += data.samples.length;
      } else if (data.command === 'stop') {
        this._active = false;
      } else if (data.command === 'clear') {
        this._buffers = [];
        this._available = 0;
        this._readOffset = 0;
      }
    };
  }

  /**
   * @param {Float32Array[][]} _inputs - unused (no input)
   * @param {Float32Array[][]} outputs - output channels
   * @returns {boolean} true to keep processor alive
   */
  process(_inputs, outputs) {
    if (!this._active) return false;

    const output = outputs[0];
    if (!output || output.length === 0) return true;

    const left = output[0];
    const right = output.length > 1 ? output[1] : null;
    const framesNeeded = left.length;

    // Assume stereo interleaved (L,R,L,R,...)
    const samplesNeeded = framesNeeded * 2;

    if (this._available < samplesNeeded) {
      // Underrun — output silence
      left.fill(0);
      if (right) right.fill(0);
      this.port.postMessage({ type: 'underrun' });
      return true;
    }

    // Read interleaved samples and deinterleave to output channels
    let written = 0;
    while (written < framesNeeded && this._buffers.length > 0) {
      const buf = this._buffers[0];
      const remaining = buf.length - this._readOffset;
      const framesToRead = Math.min(
        Math.floor(remaining / 2),
        framesNeeded - written
      );

      for (let i = 0; i < framesToRead; i++) {
        const idx = this._readOffset + i * 2;
        left[written + i] = buf[idx];
        if (right) right[written + i] = buf[idx + 1];
      }

      this._readOffset += framesToRead * 2;
      this._available -= framesToRead * 2;
      written += framesToRead;

      if (this._readOffset >= buf.length) {
        this._buffers.shift();
        this._readOffset = 0;
      }
    }

    // Fill remaining with silence if buffer ran short
    for (let i = written; i < framesNeeded; i++) {
      left[i] = 0;
      if (right) right[i] = 0;
    }

    this._samplesPlayed += written;

    // Periodically report progress
    if (this._samplesPlayed % (4096 * 4) < framesNeeded) {
      this.port.postMessage({
        type: 'samplesPlayed',
        count: this._samplesPlayed,
        available: this._available,
      });
    }

    return true;
  }
}

registerProcessor('auralis-playback-processor', AuralisPlaybackProcessor);
