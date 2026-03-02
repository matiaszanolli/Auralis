/**
 * Consolidated Performance Optimization System
 *
 * Unified module combining:
 * - VisualizationOptimizer (frame rate control, data decimation, canvas pooling)
 * - AdvancedPerformanceOptimizer (adaptive quality profiles, metrics tracking)
 * - SmoothAnimationEngine easing functions
 *
 * Provides comprehensive performance optimization for real-time audio visualization
 * with adaptive quality, frame dropping, resource management, and smooth animations.
 */

import React from 'react';

// ============================================================================
// Core Performance Types & Interfaces
// ============================================================================

export interface PerformanceMetrics {
  fps: number;
  frameTime: number;
  renderTime: number;
  cpuUsage: number;
  memoryUsage: number;
  droppedFrames: number;
  adaptiveQuality: number;
  dataPoints: number;
  bufferHealth: number;
  networkLatency?: number;
}

export interface QualitySettings {
  renderScale: number;        // 0.1 to 1.0
  dataDecimation: number;     // 1 to 10 (skip every N points)
  updateRate: number;         // Hz
  smoothingFactor: number;    // 0 to 1
  enableAAA: boolean;         // Anti-aliasing
  enableShadows: boolean;     // Shadow effects
  enableGlow: boolean;        // Glow effects
  enableAnimations: boolean;  // Smooth animations
  maxDataPoints: number;      // Maximum data points to render
}

export interface AdaptiveProfile {
  name: string;
  description: string;
  quality: QualitySettings;
  triggers: {
    cpuThreshold: number;
    fpsThreshold: number;
    memoryThreshold: number;
  };
}

export interface PerformanceConfig {
  targetFPS: number;
  maxDataPoints: number;
  decimationThreshold: number;
  canvasPoolSize: number;
  enableWebGL: boolean;
  enableOffscreenCanvas: boolean;
  adaptiveQuality: boolean;
}

// ============================================================================
// Easing Functions (unified from SmoothAnimationEngine)
// ============================================================================

export const EasingFunctions = {
  linear: (t: number) => t,
  easeInQuad: (t: number) => t * t,
  easeOutQuad: (t: number) => t * (2 - t),
  easeInOutQuad: (t: number) => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
  easeInCubic: (t: number) => t * t * t,
  easeOutCubic: (t: number) => (--t) * t * t + 1,
  easeInOutCubic: (t: number) => t < 0.5 ? 4 * t * t * t : (t - 1) * (2 * t - 2) * (2 * t - 2) + 1,
  easeInQuart: (t: number) => t * t * t * t,
  easeOutQuart: (t: number) => 1 - (--t) * t * t * t,
  easeInOutQuart: (t: number) => t < 0.5 ? 8 * t * t * t * t : 1 - 8 * (--t) * t * t * t,
  easeInElastic: (t: number) => {
    if (t === 0 || t === 1) return t;
    const p = 0.3;
    const s = p / 4;
    return -(Math.pow(2, 10 * (t -= 1)) * Math.sin((t - s) * (2 * Math.PI) / p));
  },
  easeOutElastic: (t: number) => {
    if (t === 0 || t === 1) return t;
    const p = 0.3;
    const s = p / 4;
    return Math.pow(2, -10 * t) * Math.sin((t - s) * (2 * Math.PI) / p) + 1;
  },
  easeInBounce: (t: number) => 1 - EasingFunctions.easeOutBounce(1 - t),
  easeOutBounce: (t: number) => {
    if (t < 1 / 2.75) {
      return 7.5625 * t * t;
    } else if (t < 2 / 2.75) {
      return 7.5625 * (t -= 1.5 / 2.75) * t + 0.75;
    } else if (t < 2.5 / 2.75) {
      return 7.5625 * (t -= 2.25 / 2.75) * t + 0.9375;
    } else {
      return 7.5625 * (t -= 2.625 / 2.75) * t + 0.984375;
    }
  },
  audioTaper: (t: number) => Math.pow(t, 2.2),
  smoothStep: (t: number) => t * t * (3 - 2 * t),
};

export type EasingFunction = keyof typeof EasingFunctions;

// ============================================================================
// FPS Tracking (unified)
// ============================================================================

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

    if (elapsed >= 1000) {
      this.currentFPS = (this.frameCount * 1000) / elapsed;
      this.fpsHistory.push(this.currentFPS);

      if (this.fpsHistory.length > 60) {
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

// ============================================================================
// Data Decimation
// ============================================================================

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

    for (let i = 0; i < data.length; i += step) {
      const chunk = data.slice(i, Math.min(i + step, data.length));
      const min = Math.min(...chunk);
      const max = Math.max(...chunk);

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

      if (ratio > 10) {
        const rms = Math.sqrt(chunk.reduce((sum, val) => sum + val * val, 0) / chunk.length);
        decimated.push(rms);
      } else {
        const peak = Math.max(...chunk.map(Math.abs));
        decimated.push(peak);
      }
    }

    return decimated;
  }
}

// ============================================================================
// Canvas Pooling (from VisualizationOptimizer)
// ============================================================================

export class CanvasPool {
  private pool: HTMLCanvasElement[] = [];
  private inUse: Set<HTMLCanvasElement> = new Set();
  private maxSize: number;

  constructor(maxSize: number = 10) {
    this.maxSize = maxSize;
  }

  getCanvas(width: number, height: number): HTMLCanvasElement {
    for (const canvas of this.pool) {
      if (!this.inUse.has(canvas) && canvas.width === width && canvas.height === height) {
        this.inUse.add(canvas);
        return canvas;
      }
    }

    if (this.pool.length < this.maxSize) {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      this.pool.push(canvas);
      this.inUse.add(canvas);
      return canvas;
    }

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

// ============================================================================
// Performance Monitoring (unified from both optimizers)
// ============================================================================

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

// ============================================================================
// Main Consolidated Performance Optimizer
// ============================================================================

export class PerformanceOptimizer {
  private metrics: PerformanceMetrics;
  private currentProfile: AdaptiveProfile;
  private profiles: AdaptiveProfile[];
  private frameController: FrameRateController;
  private dataDecimator: DataDecimator;
  private canvasPool: CanvasPool;
  private performanceMonitor: PerformanceMonitor;
  private frameHistory: number[] = [];
  private performanceCallbacks: ((metrics: PerformanceMetrics) => void)[] = [];
  private animationFrameId: number | null = null;
  private lastFrameTime = 0;
  private frameStartTime = 0;
  private isOptimizing = false;
  private observer?: PerformanceObserver;
  private memoryUsageInterval?: number;

  constructor(config: Partial<PerformanceConfig> = {}) {
    // Initialize config with defaults
    const fullConfig: PerformanceConfig = {
      targetFPS: 60,
      maxDataPoints: 1000,
      decimationThreshold: 2000,
      canvasPoolSize: 10,
      enableWebGL: true,
      enableOffscreenCanvas: true,
      adaptiveQuality: true,
      ...config
    };

    // Initialize metrics
    this.metrics = {
      fps: 0,
      frameTime: 16.67,
      renderTime: 0,
      cpuUsage: 0,
      memoryUsage: 0,
      droppedFrames: 0,
      adaptiveQuality: 1.0,
      dataPoints: 0,
      bufferHealth: 1.0,
    };

    // Initialize components
    this.frameController = new FrameRateController(fullConfig.targetFPS);
    this.dataDecimator = new DataDecimator(fullConfig.maxDataPoints, fullConfig.decimationThreshold);
    this.canvasPool = new CanvasPool(fullConfig.canvasPoolSize);
    this.performanceMonitor = new PerformanceMonitor();

    // Initialize profiles
    this.profiles = this.createAdaptiveProfiles();
    this.currentProfile = this.profiles[1]; // Start with 'balanced'

    // Initialize monitoring
    this.initializePerformanceMonitoring();
  }

  private createAdaptiveProfiles(): AdaptiveProfile[] {
    return [
      {
        name: 'ultra',
        description: 'Maximum Quality - Studio Monitoring',
        quality: {
          renderScale: 1.0,
          dataDecimation: 1,
          updateRate: 60,
          smoothingFactor: 0.1,
          enableAAA: true,
          enableShadows: true,
          enableGlow: true,
          enableAnimations: true,
          maxDataPoints: 8192,
        },
        triggers: {
          cpuThreshold: 90,
          fpsThreshold: 55,
          memoryThreshold: 2048,
        },
      },
      {
        name: 'balanced',
        description: 'Balanced Performance - Professional Use',
        quality: {
          renderScale: 0.8,
          dataDecimation: 2,
          updateRate: 30,
          smoothingFactor: 0.3,
          enableAAA: true,
          enableShadows: false,
          enableGlow: true,
          enableAnimations: true,
          maxDataPoints: 4096,
        },
        triggers: {
          cpuThreshold: 70,
          fpsThreshold: 25,
          memoryThreshold: 1024,
        },
      },
      {
        name: 'performance',
        description: 'Performance Mode - Real-time Critical',
        quality: {
          renderScale: 0.6,
          dataDecimation: 4,
          updateRate: 20,
          smoothingFactor: 0.5,
          enableAAA: false,
          enableShadows: false,
          enableGlow: false,
          enableAnimations: true,
          maxDataPoints: 2048,
        },
        triggers: {
          cpuThreshold: 50,
          fpsThreshold: 15,
          memoryThreshold: 512,
        },
      },
      {
        name: 'minimal',
        description: 'Minimal Resources - Emergency Mode',
        quality: {
          renderScale: 0.4,
          dataDecimation: 8,
          updateRate: 10,
          smoothingFactor: 0.7,
          enableAAA: false,
          enableShadows: false,
          enableGlow: false,
          enableAnimations: false,
          maxDataPoints: 1024,
        },
        triggers: {
          cpuThreshold: 30,
          fpsThreshold: 8,
          memoryThreshold: 256,
        },
      },
    ];
  }

  private initializePerformanceMonitoring(): void {
    if ('PerformanceObserver' in window) {
      this.observer = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        entries.forEach((entry) => {
          if (entry.entryType === 'measure' && entry.name.startsWith('auralis-render')) {
            this.metrics.renderTime = entry.duration;
          }
        });
      });

      this.observer.observe({ entryTypes: ['measure'] });
    }

    this.memoryUsageInterval = window.setInterval(() => {
      if ('memory' in performance) {
        const memInfo = (performance as any).memory;
        this.metrics.memoryUsage = memInfo.usedJSHeapSize / (1024 * 1024);
      }
    }, 1000);

    this.startFrameMonitoring();
  }

  private startFrameMonitoring(): void {
    const measureFrame = (timestamp: number) => {
      if (this.lastFrameTime > 0) {
        const deltaTime = timestamp - this.lastFrameTime;
        this.frameHistory.push(deltaTime);

        if (this.frameHistory.length > 60) {
          this.frameHistory.shift();
        }

        const avgFrameTime = this.frameHistory.reduce((a, b) => a + b, 0) / this.frameHistory.length;
        this.metrics.fps = 1000 / avgFrameTime;
        this.metrics.frameTime = avgFrameTime;

        this.updateAdaptiveQuality();
      }

      this.lastFrameTime = timestamp;
      this.animationFrameId = requestAnimationFrame(measureFrame);
    };

    this.animationFrameId = requestAnimationFrame(measureFrame);
  }

  private updateAdaptiveQuality(): void {
    if (this.isOptimizing) return;

    const { fps, cpuUsage, memoryUsage } = this.metrics;
    const profile = this.currentProfile;

    if (
      fps < profile.triggers.fpsThreshold ||
      cpuUsage > profile.triggers.cpuThreshold ||
      memoryUsage > profile.triggers.memoryThreshold
    ) {
      this.downgradeQuality();
    } else if (
      fps > profile.triggers.fpsThreshold + 10 &&
      cpuUsage < profile.triggers.cpuThreshold - 20 &&
      memoryUsage < profile.triggers.memoryThreshold - 200
    ) {
      this.upgradeQuality();
    }

    this.metrics.adaptiveQuality = Math.max(0.1, Math.min(1.0, fps / 60));
  }

  private downgradeQuality(): void {
    const currentIndex = this.profiles.findIndex(p => p.name === this.currentProfile.name);
    if (currentIndex < this.profiles.length - 1) {
      this.isOptimizing = true;
      this.currentProfile = this.profiles[currentIndex + 1];
      console.log(`🔽 Quality downgraded to: ${this.currentProfile.name}`);
      this.notifyPerformanceChange();

      setTimeout(() => {
        this.isOptimizing = false;
      }, 2000);
    }
  }

  private upgradeQuality(): void {
    const currentIndex = this.profiles.findIndex(p => p.name === this.currentProfile.name);
    if (currentIndex > 0) {
      this.isOptimizing = true;
      this.currentProfile = this.profiles[currentIndex - 1];
      console.log(`🔼 Quality upgraded to: ${this.currentProfile.name}`);
      this.notifyPerformanceChange();

      setTimeout(() => {
        this.isOptimizing = false;
      }, 5000);
    }
  }

  private notifyPerformanceChange(): void {
    this.performanceCallbacks.forEach(callback => {
      callback(this.getMetrics());
    });
  }

  // ========================================================================
  // Public API - Data Optimization
  // ========================================================================

  optimizeData(data: number[]): number[] {
    let optimizedData = data;

    if (data.length > this.currentProfile.quality.maxDataPoints) {
      const targetPoints = Math.floor(this.currentProfile.quality.maxDataPoints * this.metrics.adaptiveQuality);
      optimizedData = this.dataDecimator.adaptiveDecimate(data, targetPoints);
    }

    this.metrics.dataPoints = optimizedData.length;
    this.performanceMonitor.end('data-optimization');

    return optimizedData;
  }

  optimizeDataArray<T>(data: T[]): T[] {
    const { dataDecimation, maxDataPoints } = this.currentProfile.quality;

    if (!data || data.length === 0) return data;

    let optimizedData = data;

    if (dataDecimation > 1) {
      optimizedData = data.filter((_, index) => index % dataDecimation === 0);
    }

    if (optimizedData.length > maxDataPoints) {
      const step = Math.ceil(optimizedData.length / maxDataPoints);
      optimizedData = optimizedData.filter((_, index) => index % step === 0);
    }

    this.metrics.dataPoints = optimizedData.length;
    return optimizedData;
  }

  // ========================================================================
  // Public API - Render Management
  // ========================================================================

  shouldRender(): boolean {
    const currentTime = performance.now();
    const shouldRender = this.frameController.shouldRender(currentTime);

    if (shouldRender) {
      this.frameController.updateFPS(currentTime);
      this.metrics.fps = this.frameController.getFPS();
      this.metrics.droppedFrames = this.frameController.getDroppedFrames();
    }

    return shouldRender;
  }

  startRender(): void {
    this.frameStartTime = performance.now();
    this.performanceMonitor.start('render-cycle');
    if ('performance' in window) {
      performance.mark('auralis-render-start');
    }
  }

  endRender(): void {
    const renderTime = performance.now() - this.frameStartTime;
    this.metrics.renderTime = renderTime;
    this.performanceMonitor.end('render-cycle');

    if ('performance' in window) {
      performance.mark('auralis-render-end');
      performance.measure('auralis-render', 'auralis-render-start', 'auralis-render-end');
    }
  }

  // ========================================================================
  // Public API - Canvas Management
  // ========================================================================

  getCanvas(width: number, height: number): HTMLCanvasElement {
    return this.canvasPool.getCanvas(width, height);
  }

  releaseCanvas(canvas: HTMLCanvasElement): void {
    this.canvasPool.releaseCanvas(canvas);
  }

  getOptimizedCanvasSize(baseWidth: number, baseHeight: number): { width: number; height: number } {
    const scale = this.currentProfile.quality.renderScale;
    return {
      width: Math.round(baseWidth * scale),
      height: Math.round(baseHeight * scale),
    };
  }

  // ========================================================================
  // Public API - Quality Management
  // ========================================================================

  shouldUseEffect(effectType: 'shadows' | 'glow' | 'antialiasing' | 'animations'): boolean {
    const quality = this.currentProfile.quality;

    switch (effectType) {
      case 'shadows': return quality.enableShadows;
      case 'glow': return quality.enableGlow;
      case 'antialiasing': return quality.enableAAA;
      case 'animations': return quality.enableAnimations;
      default: return true;
    }
  }

  getSmoothingFactor(): number {
    return this.currentProfile.quality.smoothingFactor;
  }

  getUpdateRate(): number {
    return this.currentProfile.quality.updateRate;
  }

  getQualityLevel(): number {
    return this.metrics.adaptiveQuality;
  }

  // ========================================================================
  // Public API - Metrics & Monitoring
  // ========================================================================

  getMetrics(): PerformanceMetrics {
    return { ...this.metrics };
  }

  getCurrentProfile(): AdaptiveProfile {
    return { ...this.currentProfile };
  }

  setProfile(profileName: string): void {
    const profile = this.profiles.find(p => p.name === profileName);
    if (profile) {
      this.currentProfile = profile;
      this.notifyPerformanceChange();
    }
  }

  onPerformanceChange(callback: (metrics: PerformanceMetrics) => void): void {
    this.performanceCallbacks.push(callback);
  }

  updateCPUUsage(): void {
    if (this.frameHistory.length > 10) {
      const avgFrameTime = this.frameHistory.slice(-10).reduce((a, b) => a + b, 0) / 10;
      const targetFrameTime = 1000 / 60;

      this.metrics.cpuUsage = Math.min(100, (avgFrameTime / targetFrameTime) * 50);
    }
  }

  updateBufferHealth(bufferLevel: number, maxBuffer: number): void {
    this.metrics.bufferHealth = Math.max(0, Math.min(1, bufferLevel / maxBuffer));
  }

  updateNetworkLatency(latency: number): void {
    this.metrics.networkLatency = latency;
  }

  getPerformanceMonitor(): PerformanceMonitor {
    return this.performanceMonitor;
  }

  exportPerformanceReport(): string {
    const report = {
      timestamp: new Date().toISOString(),
      session: {
        duration: Date.now() - (this.lastFrameTime || Date.now()),
        totalFrames: this.frameHistory.length,
        droppedFrames: this.metrics.droppedFrames,
      },
      currentMetrics: this.metrics,
      currentProfile: this.currentProfile.name,
      frameHistory: this.frameHistory.slice(-100),
      averagePerformance: {
        avgFPS: this.frameHistory.length > 0 ?
          1000 / (this.frameHistory.reduce((a, b) => a + b, 0) / this.frameHistory.length) : 0,
        maxFrameTime: Math.max(...this.frameHistory),
        minFrameTime: Math.min(...this.frameHistory),
      },
    };

    return JSON.stringify(report, null, 2);
  }

  // ========================================================================
  // Cleanup
  // ========================================================================

  cleanup(): void {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }

    if (this.observer) {
      this.observer.disconnect();
    }

    if (this.memoryUsageInterval) {
      clearInterval(this.memoryUsageInterval);
    }

    this.canvasPool.cleanup();
    this.performanceMonitor.clear();
    this.performanceCallbacks = [];
  }
}

// ============================================================================
// Global Instance & React Hook
// ============================================================================

export const globalPerformanceOptimizer = new PerformanceOptimizer();

export function usePerformanceOptimization() {
  const [metrics, setMetrics] = React.useState<PerformanceMetrics>(globalPerformanceOptimizer.getMetrics());
  const [profile, setProfile] = React.useState<AdaptiveProfile>(globalPerformanceOptimizer.getCurrentProfile());

  React.useEffect(() => {
    const handlePerformanceChange = (newMetrics: PerformanceMetrics) => {
      setMetrics(newMetrics);
      setProfile(globalPerformanceOptimizer.getCurrentProfile());
    };

    globalPerformanceOptimizer.onPerformanceChange(handlePerformanceChange);

    return () => {
      // Cleanup handled by global optimizer
    };
  }, []);

  return {
    metrics,
    profile,
    optimizer: globalPerformanceOptimizer,
    shouldRender: () => globalPerformanceOptimizer.shouldRender(),
    startRender: () => globalPerformanceOptimizer.startRender(),
    endRender: () => globalPerformanceOptimizer.endRender(),
    optimizeData: (data: number[]) => globalPerformanceOptimizer.optimizeData(data),
    optimizeDataArray: <T,>(data: T[]) => globalPerformanceOptimizer.optimizeDataArray(data),
    shouldUseEffect: (effect: 'shadows' | 'glow' | 'antialiasing' | 'animations') =>
      globalPerformanceOptimizer.shouldUseEffect(effect),
    getCanvasSize: (w: number, h: number) => globalPerformanceOptimizer.getOptimizedCanvasSize(w, h),
    getCanvas: (w: number, h: number) => globalPerformanceOptimizer.getCanvas(w, h),
    releaseCanvas: (c: HTMLCanvasElement) => globalPerformanceOptimizer.releaseCanvas(c),
    getSmoothingFactor: () => globalPerformanceOptimizer.getSmoothingFactor(),
    exportReport: () => globalPerformanceOptimizer.exportPerformanceReport(),
  };
}

export default PerformanceOptimizer;
