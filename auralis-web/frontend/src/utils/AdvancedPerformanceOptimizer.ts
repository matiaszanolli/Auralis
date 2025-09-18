/**
 * Advanced Performance Optimizer for Phase 5.3 Real-time Updates
 *
 * This system provides comprehensive performance optimization for real-time
 * audio visualization with adaptive quality, frame dropping, and resource management.
 */

interface PerformanceMetrics {
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

interface QualitySettings {
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

interface AdaptiveProfile {
  name: string;
  description: string;
  quality: QualitySettings;
  triggers: {
    cpuThreshold: number;
    fpsThreshold: number;
    memoryThreshold: number;
  };
}

export class AdvancedPerformanceOptimizer {
  private metrics: PerformanceMetrics;
  private currentProfile: AdaptiveProfile;
  private profiles: AdaptiveProfile[];
  private frameHistory: number[] = [];
  private performanceCallbacks: ((metrics: PerformanceMetrics) => void)[] = [];
  private animationFrameId: number | null = null;
  private lastFrameTime = 0;
  private frameStartTime = 0;
  private isOptimizing = false;

  // Performance monitoring
  private observer?: PerformanceObserver;
  private memoryUsageInterval?: number;

  constructor() {
    this.metrics = {
      fps: 0,
      frameTime: 16.67, // 60fps baseline
      renderTime: 0,
      cpuUsage: 0,
      memoryUsage: 0,
      droppedFrames: 0,
      adaptiveQuality: 1.0,
      dataPoints: 0,
      bufferHealth: 1.0,
    };

    this.profiles = this.createAdaptiveProfiles();
    this.currentProfile = this.profiles[1]; // Start with 'balanced'

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
    // Performance Observer for detailed metrics
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

    // Memory usage monitoring
    this.memoryUsageInterval = window.setInterval(() => {
      if ('memory' in performance) {
        const memInfo = (performance as any).memory;
        this.metrics.memoryUsage = memInfo.usedJSHeapSize / (1024 * 1024); // MB
      }
    }, 1000);

    // Frame rate monitoring
    this.startFrameMonitoring();
  }

  private startFrameMonitoring(): void {
    const measureFrame = (timestamp: number) => {
      if (this.lastFrameTime > 0) {
        const deltaTime = timestamp - this.lastFrameTime;
        this.frameHistory.push(deltaTime);

        // Keep only last 60 frames for FPS calculation
        if (this.frameHistory.length > 60) {
          this.frameHistory.shift();
        }

        // Calculate FPS
        const avgFrameTime = this.frameHistory.reduce((a, b) => a + b, 0) / this.frameHistory.length;
        this.metrics.fps = 1000 / avgFrameTime;
        this.metrics.frameTime = avgFrameTime;

        // Update adaptive quality based on performance
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

    // Check if we need to downgrade quality
    if (
      fps < profile.triggers.fpsThreshold ||
      cpuUsage > profile.triggers.cpuThreshold ||
      memoryUsage > profile.triggers.memoryThreshold
    ) {
      this.downgradeQuality();
    }
    // Check if we can upgrade quality
    else if (
      fps > profile.triggers.fpsThreshold + 10 &&
      cpuUsage < profile.triggers.cpuThreshold - 20 &&
      memoryUsage < profile.triggers.memoryThreshold - 200
    ) {
      this.upgradeQuality();
    }

    // Update adaptive quality factor
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
      }, 2000); // Prevent rapid quality changes
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
      }, 5000); // Be more conservative about upgrades
    }
  }

  private notifyPerformanceChange(): void {
    this.performanceCallbacks.forEach(callback => {
      callback(this.getMetrics());
    });
  }

  // Public API
  startRender(): void {
    this.frameStartTime = performance.now();
    if ('performance' in window) {
      performance.mark('auralis-render-start');
    }
  }

  endRender(): void {
    if ('performance' in window) {
      performance.mark('auralis-render-end');
      performance.measure('auralis-render', 'auralis-render-start', 'auralis-render-end');
    }
  }

  shouldRender(): boolean {
    // Frame dropping logic
    const targetFrameTime = 1000 / this.currentProfile.quality.updateRate;
    const timeSinceLastFrame = performance.now() - this.lastFrameTime;

    return timeSinceLastFrame >= targetFrameTime;
  }

  optimizeDataArray<T>(data: T[]): T[] {
    const { dataDecimation, maxDataPoints } = this.currentProfile.quality;

    if (!data || data.length === 0) return data;

    let optimizedData = data;

    // Apply decimation (skip points)
    if (dataDecimation > 1) {
      optimizedData = data.filter((_, index) => index % dataDecimation === 0);
    }

    // Limit maximum data points
    if (optimizedData.length > maxDataPoints) {
      const step = Math.ceil(optimizedData.length / maxDataPoints);
      optimizedData = optimizedData.filter((_, index) => index % step === 0);
    }

    this.metrics.dataPoints = optimizedData.length;
    return optimizedData;
  }

  getOptimizedCanvasSize(baseWidth: number, baseHeight: number): { width: number; height: number } {
    const scale = this.currentProfile.quality.renderScale;
    return {
      width: Math.round(baseWidth * scale),
      height: Math.round(baseHeight * scale),
    };
  }

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

  // CPU usage estimation based on frame timing
  updateCPUUsage(): void {
    if (this.frameHistory.length > 10) {
      const avgFrameTime = this.frameHistory.slice(-10).reduce((a, b) => a + b, 0) / 10;
      const targetFrameTime = 1000 / 60; // 60fps baseline

      // Estimate CPU usage based on frame time deviation
      this.metrics.cpuUsage = Math.min(100, (avgFrameTime / targetFrameTime) * 50);
    }
  }

  // Buffer health monitoring for real-time audio
  updateBufferHealth(bufferLevel: number, maxBuffer: number): void {
    this.metrics.bufferHealth = Math.max(0, Math.min(1, bufferLevel / maxBuffer));
  }

  // Network latency for remote audio sources
  updateNetworkLatency(latency: number): void {
    this.metrics.networkLatency = latency;
  }

  // Export performance report
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
      frameHistory: this.frameHistory.slice(-100), // Last 100 frames
      averagePerformance: {
        avgFPS: this.frameHistory.length > 0 ?
          1000 / (this.frameHistory.reduce((a, b) => a + b, 0) / this.frameHistory.length) : 0,
        maxFrameTime: Math.max(...this.frameHistory),
        minFrameTime: Math.min(...this.frameHistory),
      },
    };

    return JSON.stringify(report, null, 2);
  }

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

    this.performanceCallbacks = [];
  }
}

// Global performance optimizer instance
export const globalPerformanceOptimizer = new AdvancedPerformanceOptimizer();

// React hook for advanced performance optimization
export function useAdvancedPerformanceOptimization() {
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
    optimizeData: <T>(data: T[]) => globalPerformanceOptimizer.optimizeDataArray(data),
    shouldUseEffect: (effect: 'shadows' | 'glow' | 'antialiasing' | 'animations') =>
      globalPerformanceOptimizer.shouldUseEffect(effect),
    getCanvasSize: (w: number, h: number) => globalPerformanceOptimizer.getOptimizedCanvasSize(w, h),
    exportReport: () => globalPerformanceOptimizer.exportPerformanceReport(),
  };
}

// Import React for the hook
import React from 'react';

export default AdvancedPerformanceOptimizer;