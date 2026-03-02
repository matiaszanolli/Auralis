/**
 * Visualization Performance Optimizer
 *
 * Provides utilities for optimizing real-time audio visualization performance
 * including frame rate management, data decimation, and rendering optimization.
 */

export interface PerformanceConfig {
  targetFPS: number;
  maxDataPoints: number;
  decimationThreshold: number;
  canvasPoolSize: number;
  enableWebGL: boolean;
  enableOffscreenCanvas: boolean;
  adaptiveQuality: boolean;
}

export interface RenderStats {
  fps: number;
  frameTime: number;
  renderTime: number;
  dataPoints: number;
  memoryUsage: number;
  droppedFrames: number;
}

export class FrameRateController {
  private frameInterval: number;
  private lastFrameTime: number = 0;
  private frameCount: number = 0;
  private currentFPS: number = 0;
  private fpsHistory: number[] = [];
  private droppedFrames: number = 0;

  constructor(targetFPS: number = 60) {
    this.frameInterval = 1000 / targetFPS;
  }

  shouldRender(currentTime: number): boolean {
    const elapsed = currentTime - this.lastFrameTime;

    if (elapsed >= this.frameInterval) {
      this.lastFrameTime = currentTime;
      this.frameCount++;
      return true;
    }

    this.droppedFrames++;
    return false;
  }

  updateFPS(_currentTime: number): void {
    this.frameCount++;
    const now = performance.now();
    const elapsed = now - this.lastFrameTime;

    if (elapsed >= 1000) { // Update FPS every second
      this.currentFPS = (this.frameCount * 1000) / elapsed;
      this.fpsHistory.push(this.currentFPS);

      if (this.fpsHistory.length > 60) { // Keep 60 seconds of history
        this.fpsHistory.shift();
      }

      this.frameCount = 0;
      this.lastFrameTime = now;
    }
  }

  getFPS(): number {
    return this.currentFPS;
  }

  getAverageFPS(): number {
    if (this.fpsHistory.length === 0) return 0;
    return this.fpsHistory.reduce((sum, fps) => sum + fps, 0) / this.fpsHistory.length;
  }

  getDroppedFrames(): number {
    return this.droppedFrames;
  }

  adjustTargetFPS(newFPS: number): void {
    this.frameInterval = 1000 / newFPS;
  }
}

export class DataDecimator {
  private maxPoints: number;

  constructor(maxPoints: number = 1000, _threshold: number = 2000) {
    this.maxPoints = maxPoints;
  }

  decimate(data: number[]): number[] {
    if (data.length <= this.maxPoints) {
      return data;
    }

    const step = Math.ceil(data.length / this.maxPoints);
    const decimated: number[] = [];

    // Use min-max decimation for audio data to preserve peaks
    for (let i = 0; i < data.length; i += step) {
      const chunk = data.slice(i, Math.min(i + step, data.length));
      const min = Math.min(...chunk);
      const max = Math.max(...chunk);

      // Alternate between min and max to preserve waveform shape
      if (decimated.length % 2 === 0) {
        decimated.push(max);
      } else {
        decimated.push(min);
      }
    }

    return decimated;
  }

  adaptiveDecimate(data: number[], targetPoints: number): number[] {
    if (data.length <= targetPoints) {
      return data;
    }

    const ratio = data.length / targetPoints;
    const decimated: number[] = [];

    for (let i = 0; i < targetPoints; i++) {
      const start = Math.floor(i * ratio);
      const end = Math.floor((i + 1) * ratio);
      const chunk = data.slice(start, end);

      if (chunk.length === 0) continue;

      // Use RMS for smoother visualization at high decimation ratios
      if (ratio > 10) {
        const rms = Math.sqrt(chunk.reduce((sum, val) => sum + val * val, 0) / chunk.length);
        decimated.push(rms);
      } else {
        // Use peak detection for lower decimation ratios
        const peak = Math.max(...chunk.map(Math.abs));
        decimated.push(peak);
      }
    }

    return decimated;
  }
}

export class CanvasPool {
  private pool: HTMLCanvasElement[] = [];
  private inUse: Set<HTMLCanvasElement> = new Set();
  private maxSize: number;

  constructor(maxSize: number = 10) {
    this.maxSize = maxSize;
  }

  getCanvas(width: number, height: number): HTMLCanvasElement {
    // Try to find an unused canvas with matching dimensions
    for (const canvas of this.pool) {
      if (!this.inUse.has(canvas) && canvas.width === width && canvas.height === height) {
        this.inUse.add(canvas);
        return canvas;
      }
    }

    // Create new canvas if pool has space
    if (this.pool.length < this.maxSize) {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      this.pool.push(canvas);
      this.inUse.add(canvas);
      return canvas;
    }

    // Reuse oldest canvas
    const canvas = this.pool[0];
    if (this.inUse.has(canvas)) {
      this.inUse.delete(canvas);
    }
    canvas.width = width;
    canvas.height = height;
    this.inUse.add(canvas);
    return canvas;
  }

  releaseCanvas(canvas: HTMLCanvasElement): void {
    this.inUse.delete(canvas);
  }

  cleanup(): void {
    this.pool.forEach(canvas => {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    });
    this.inUse.clear();
  }
}

export class RenderOptimizer {
  private frameController: FrameRateController;
  private dataDecimator: DataDecimator;
  private canvasPool: CanvasPool;
  private config: PerformanceConfig;
  private stats: RenderStats;
  private lastRenderTime: number = 0;
  private adaptiveQualityLevel: number = 1.0;

  constructor(config: Partial<PerformanceConfig> = {}) {
    this.config = {
      targetFPS: 60,
      maxDataPoints: 1000,
      decimationThreshold: 2000,
      canvasPoolSize: 10,
      enableWebGL: true,
      enableOffscreenCanvas: true,
      adaptiveQuality: true,
      ...config
    };

    this.frameController = new FrameRateController(this.config.targetFPS);
    this.dataDecimator = new DataDecimator(this.config.maxDataPoints, this.config.decimationThreshold);
    this.canvasPool = new CanvasPool(this.config.canvasPoolSize);

    this.stats = {
      fps: 0,
      frameTime: 0,
      renderTime: 0,
      dataPoints: 0,
      memoryUsage: 0,
      droppedFrames: 0
    };
  }

  optimizeData(data: number[]): number[] {
    let optimizedData = data;

    // Apply decimation if needed
    if (data.length > this.config.decimationThreshold) {
      const targetPoints = Math.floor(this.config.maxDataPoints * this.adaptiveQualityLevel);
      optimizedData = this.dataDecimator.adaptiveDecimate(data, targetPoints);
    }

    this.stats.dataPoints = optimizedData.length;

    return optimizedData;
  }

  shouldRender(): boolean {
    const currentTime = performance.now();
    const shouldRender = this.frameController.shouldRender(currentTime);

    if (shouldRender) {
      this.frameController.updateFPS(currentTime);
      this.updateStats();
    }

    return shouldRender;
  }

  startRender(): void {
    this.lastRenderTime = performance.now();
  }

  endRender(): void {
    const renderTime = performance.now() - this.lastRenderTime;
    this.stats.renderTime = renderTime;

    // Adaptive quality adjustment
    if (this.config.adaptiveQuality) {
      this.adjustQuality(renderTime);
    }
  }

  private adjustQuality(renderTime: number): void {
    const targetFrameTime = 1000 / this.config.targetFPS;
    const currentFPS = this.frameController.getFPS();

    // Decrease quality if we're dropping frames or render time is too high
    if (currentFPS < this.config.targetFPS * 0.8 || renderTime > targetFrameTime * 1.5) {
      this.adaptiveQualityLevel = Math.max(0.25, this.adaptiveQualityLevel * 0.9);
    }
    // Increase quality if we have headroom
    else if (currentFPS > this.config.targetFPS * 0.95 && renderTime < targetFrameTime * 0.7) {
      this.adaptiveQualityLevel = Math.min(1.0, this.adaptiveQualityLevel * 1.05);
    }
  }

  private updateStats(): void {
    this.stats.fps = this.frameController.getFPS();
    this.stats.frameTime = 1000 / this.stats.fps;
    this.stats.droppedFrames = this.frameController.getDroppedFrames();

    // Estimate memory usage (simplified)
    if ((performance as any).memory) {
      this.stats.memoryUsage = (performance as any).memory.usedJSHeapSize / 1024 / 1024; // MB
    }
  }

  getStats(): RenderStats {
    return { ...this.stats };
  }

  getQualityLevel(): number {
    return this.adaptiveQualityLevel;
  }

  setConfig(newConfig: Partial<PerformanceConfig>): void {
    this.config = { ...this.config, ...newConfig };
    this.frameController.adjustTargetFPS(this.config.targetFPS);
  }

  cleanup(): void {
    this.canvasPool.cleanup();
  }
}

// WebGL utilities for high-performance rendering
export class WebGLRenderer {
  private gl: WebGLRenderingContext | null = null;
  private programs: Map<string, WebGLProgram> = new Map();
  private buffers: Map<string, WebGLBuffer> = new Map();

  constructor(canvas: HTMLCanvasElement) {
    this.gl = (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')) as WebGLRenderingContext | null;

    if (!this.gl) {
      console.warn('WebGL not supported, falling back to 2D canvas');
      return;
    }

    this.initializeShaders();
  }

  private initializeShaders(): void {
    if (!this.gl) return;

    // Vertex shader for waveform rendering
    const vertexShaderSource = `
      attribute vec2 a_position;
      attribute float a_amplitude;
      uniform vec2 u_resolution;
      uniform float u_scale;
      varying float v_amplitude;

      void main() {
        vec2 position = (a_position / u_resolution) * 2.0 - 1.0;
        position.y = (position.y + a_amplitude * u_scale);
        gl_Position = vec4(position * vec2(1, -1), 0, 1);
        v_amplitude = a_amplitude;
      }
    `;

    // Fragment shader for waveform rendering
    const fragmentShaderSource = `
      precision mediump float;
      varying float v_amplitude;
      uniform vec3 u_color;

      void main() {
        float intensity = abs(v_amplitude);
        gl_FragColor = vec4(u_color * intensity, 1.0);
      }
    `;

    const program = this.createProgram(vertexShaderSource, fragmentShaderSource);
    if (program) {
      this.programs.set('waveform', program);
    }
  }

  private createProgram(vertexSource: string, fragmentSource: string): WebGLProgram | null {
    if (!this.gl) return null;

    const vertexShader = this.createShader(this.gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = this.createShader(this.gl.FRAGMENT_SHADER, fragmentSource);

    if (!vertexShader || !fragmentShader) return null;

    const program = this.gl.createProgram();
    if (!program) return null;

    this.gl.attachShader(program, vertexShader);
    this.gl.attachShader(program, fragmentShader);
    this.gl.linkProgram(program);

    if (!this.gl.getProgramParameter(program, this.gl.LINK_STATUS)) {
      console.error('Error linking program:', this.gl.getProgramInfoLog(program));
      return null;
    }

    return program;
  }

  private createShader(type: number, source: string): WebGLShader | null {
    if (!this.gl) return null;

    const shader = this.gl.createShader(type);
    if (!shader) return null;

    this.gl.shaderSource(shader, source);
    this.gl.compileShader(shader);

    if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
      console.error('Error compiling shader:', this.gl.getShaderInfoLog(shader));
      this.gl.deleteShader(shader);
      return null;
    }

    return shader;
  }

  renderWaveform(data: Float32Array, width: number, height: number): void {
    if (!this.gl) return;

    const program = this.programs.get('waveform');
    if (!program) return;

    this.gl.useProgram(program);
    this.gl.viewport(0, 0, width, height);

    // Set up vertex data
    const positions = new Float32Array(data.length * 2);
    for (let i = 0; i < data.length; i++) {
      positions[i * 2] = (i / data.length) * width;
      positions[i * 2 + 1] = height / 2;
    }

    // Create or update position buffer
    let positionBuffer = this.buffers.get('position');
    if (!positionBuffer) {
      positionBuffer = this.gl.createBuffer();
      if (positionBuffer) {
        this.buffers.set('position', positionBuffer);
      }
    }

    if (positionBuffer) {
      this.gl.bindBuffer(this.gl.ARRAY_BUFFER, positionBuffer);
      this.gl.bufferData(this.gl.ARRAY_BUFFER, positions, this.gl.DYNAMIC_DRAW);

      const positionLocation = this.gl.getAttribLocation(program, 'a_position');
      this.gl.enableVertexAttribArray(positionLocation);
      this.gl.vertexAttribPointer(positionLocation, 2, this.gl.FLOAT, false, 0, 0);
    }

    // Create or update amplitude buffer
    let amplitudeBuffer = this.buffers.get('amplitude');
    if (!amplitudeBuffer) {
      amplitudeBuffer = this.gl.createBuffer();
      if (amplitudeBuffer) {
        this.buffers.set('amplitude', amplitudeBuffer);
      }
    }

    if (amplitudeBuffer) {
      this.gl.bindBuffer(this.gl.ARRAY_BUFFER, amplitudeBuffer);
      this.gl.bufferData(this.gl.ARRAY_BUFFER, data, this.gl.DYNAMIC_DRAW);

      const amplitudeLocation = this.gl.getAttribLocation(program, 'a_amplitude');
      this.gl.enableVertexAttribArray(amplitudeLocation);
      this.gl.vertexAttribPointer(amplitudeLocation, 1, this.gl.FLOAT, false, 0, 0);
    }

    // Set uniforms
    const resolutionLocation = this.gl.getUniformLocation(program, 'u_resolution');
    this.gl.uniform2f(resolutionLocation, width, height);

    const scaleLocation = this.gl.getUniformLocation(program, 'u_scale');
    this.gl.uniform1f(scaleLocation, 1.0);

    const colorLocation = this.gl.getUniformLocation(program, 'u_color');
    this.gl.uniform3f(colorLocation, 0.3, 0.7, 1.0); // Blue color

    // Render
    this.gl.clear(this.gl.COLOR_BUFFER_BIT);
    this.gl.drawArrays(this.gl.LINE_STRIP, 0, data.length);
  }

  cleanup(): void {
    if (!this.gl) return;

    this.buffers.forEach(buffer => {
      this.gl?.deleteBuffer(buffer);
    });
    this.buffers.clear();

    this.programs.forEach(program => {
      this.gl?.deleteProgram(program);
    });
    this.programs.clear();
  }
}

// Performance monitoring utilities
export class PerformanceMonitor {
  private measurements: Map<string, number[]> = new Map();
  private startTimes: Map<string, number> = new Map();

  start(label: string): void {
    this.startTimes.set(label, performance.now());
  }

  end(label: string): number {
    const startTime = this.startTimes.get(label);
    if (!startTime) return 0;

    const duration = performance.now() - startTime;

    if (!this.measurements.has(label)) {
      this.measurements.set(label, []);
    }

    const measurements = this.measurements.get(label)!;
    measurements.push(duration);

    // Keep only last 100 measurements
    if (measurements.length > 100) {
      measurements.shift();
    }

    this.startTimes.delete(label);
    return duration;
  }

  getAverage(label: string): number {
    const measurements = this.measurements.get(label);
    if (!measurements || measurements.length === 0) return 0;

    return measurements.reduce((sum, val) => sum + val, 0) / measurements.length;
  }

  getStats(label: string): { avg: number; min: number; max: number; count: number } {
    const measurements = this.measurements.get(label);
    if (!measurements || measurements.length === 0) {
      return { avg: 0, min: 0, max: 0, count: 0 };
    }

    return {
      avg: measurements.reduce((sum, val) => sum + val, 0) / measurements.length,
      min: Math.min(...measurements),
      max: Math.max(...measurements),
      count: measurements.length
    };
  }

  clear(): void {
    this.measurements.clear();
    this.startTimes.clear();
  }
}