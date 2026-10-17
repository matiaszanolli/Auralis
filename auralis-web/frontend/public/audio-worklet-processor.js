/**
 * AudioWorkletProcessor for Auralis playback engine (#2347)
 *
 * Replaces deprecated ScriptProcessorNode with AudioWorklet.
 * Runs on the audio rendering thread (not main thread) for better performance.
 *
 * Communication protocol:
 * - Main thread sends PCM samples via port.postMessage({ samples: Float32Array })
 * - Main thread sends control messages:
 *   { command: 'stop' | 'setVolume' | 'setChannels' | 'clear' | 'pause' | 'resume' }
 *   'pause' keeps the queued PCM and the played count and outputs silence until
 *   'resume' (#5657); 'clear' discards the queue (stop / seek).
 * - Processor sends state updates: { type: 'underrun' | 'samplesPlayed', ... }
 *   `samplesPlayed` carries the absolute frame count and the frames still queued
 *   here; the main thread uses them to cap how much it feeds ahead (#5657).
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
    /** Paused: output silence, consume nothing, count nothing (#5657) */
    this._paused = false;
    /** The queue ran dry at the last render (an underrun is in progress) */
    this._starved = false;
    /** Number of interleaved channels (set via setChannels command, fixes #2842) */
    this._channels = 2;

    this.port.onmessage = (event) => {
      const { data } = event;
      if (data.samples) {
        // Receive interleaved PCM samples from the main thread. The buffer is
        // transferred (not cloned) since #5665 — use it directly; copying it
        // here allocated on the audio rendering thread per block.
        this._buffers.push(data.samples);
        this._available += data.samples.length;
      } else if (data.command === 'stop') {
        this._active = false;
      } else if (data.command === 'clear') {
        this._buffers = [];
        this._available = 0;
        this._readOffset = 0;
      } else if (data.command === 'setChannels') {
        this._channels = data.channels || 2;
      } else if (data.command === 'pause') {
        this._paused = true;
        // Exact position for the main thread: reports are otherwise ~0.37 s apart.
        this._reportProgress();
      } else if (data.command === 'resume') {
        this._paused = false;
      }
    };
  }

  _reportProgress() {
    this.port.postMessage({
      type: 'samplesPlayed',
      count: this._samplesPlayed,
      available: this._available,
    });
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

    const channels = this._channels;
    const framesNeeded = output[0].length;
    const samplesNeeded = framesNeeded * channels;

    if (this._paused) {
      // Held, not underrun: the queue is intact and playback resumes from it.
      for (let ch = 0; ch < output.length; ch++) output[ch].fill(0);
      return true;
    }

    if (this._available < samplesNeeded) {
      // Underrun — output silence
      for (let ch = 0; ch < output.length; ch++) output[ch].fill(0);

      if (!this._starved) {
        // Progress is otherwise reported every ~0.37 s, so the last report can be
        // that far short of where playback actually stopped. Send the exact count
        // as the queue runs dry — at the end of a track this is what lets the
        // position reach the duration.
        if (this._samplesPlayed > 0) this._reportProgress();
        // One underrun message per stall, not one per render quantum (#5665) —
        // process() runs ~345x/s. _starved clears when audio is produced below,
        // so a second stall after recovery posts again (#5461's signal).
        this.port.postMessage({ type: 'underrun' });
        this._starved = true;
      }
      return true;
    }

    // Read interleaved samples and deinterleave to output channels
    let written = 0;
    while (written < framesNeeded && this._buffers.length > 0) {
      const buf = this._buffers[0];
      const remaining = buf.length - this._readOffset;
      const framesToRead = Math.min(
        Math.floor(remaining / channels),
        framesNeeded - written
      );

      for (let i = 0; i < framesToRead; i++) {
        const idx = this._readOffset + i * channels;
        for (let ch = 0; ch < output.length; ch++) {
          // For mono source with stereo output, duplicate the single channel.
          // For multichannel, map channels 1:1.
          output[ch][written + i] = buf[idx + Math.min(ch, channels - 1)];
        }
      }

      this._readOffset += framesToRead * channels;
      this._available -= framesToRead * channels;
      written += framesToRead;

      if (this._readOffset >= buf.length) {
        this._buffers.shift();
        this._readOffset = 0;
      }
    }

    this._starved = false;

    // Fill remaining with silence if buffer ran short
    for (let i = written; i < framesNeeded; i++) {
      for (let ch = 0; ch < output.length; ch++) output[ch][i] = 0;
    }

    this._samplesPlayed += written;

    // Periodically report progress
    if (this._samplesPlayed % (4096 * 4) < framesNeeded) {
      this._reportProgress();
    }

    return true;
  }
}

registerProcessor('auralis-playback-processor', AuralisPlaybackProcessor);
