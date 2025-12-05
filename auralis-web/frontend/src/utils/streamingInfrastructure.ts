/**
 * Streaming Infrastructure Module
 *
 * Provides unified streaming patterns for WebSocket-based audio streaming.
 * Consolidated architecture (Phase 3 consolidation) uses WebSocket exclusively
 * for real-time audio playback with PCM streaming.
 *
 * Includes:
 * - Unified streaming metrics
 * - Configuration management
 * - State management for streaming lifecycle
 * - Callback subscription system
 * - Error handling integration
 *
 * Primary streaming: usePlayEnhanced hook + audio_stream_controller.py (WebSocket PCM)
 */

// ============================================================================
// Unified Streaming Metrics
// ============================================================================

export interface StreamingMetrics {
  // Connection metrics
  packetsReceived: number;
  packetsDropped: number;
  reconnects: number;
  connectionTime: number; // ms since connected

  // Performance metrics
  latency: number; // ms
  jitter: number; // ms
  dataRate: number; // KB/s
  throughput: number; // bytes/s

  // Buffer metrics
  bufferHealth: number; // 0-1 (1 = full, 0 = empty)
  bufferSize: number; // current items in buffer
  bufferMaxSize: number; // configured max capacity
  bufferUnderruns: number; // times buffer ran empty

  // Quality metrics
  qualityLevel: number; // 0-1 (adaptive quality)
  errorRate: number; // percentage of failed operations
  successRate: number; // percentage of successful operations
}

export interface StreamingStatus {
  isConnected: boolean;
  isStreaming: boolean;
  metrics: StreamingMetrics;
  lastUpdateTime: number;
  connectionStartTime?: number;
}

// ============================================================================
// Streaming Configuration
// ============================================================================

export interface StreamingConfig {
  // Connection settings
  autoConnect?: boolean;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
  initialReconnectDelayMs?: number;
  backoffMultiplier?: number;

  // Buffering settings
  bufferSize?: number;
  enableBuffering?: boolean;
  highWaterMark?: number; // trigger backpressure
  lowWaterMark?: number; // resume after backpressure

  // Metrics settings
  metricsUpdateIntervalMs?: number;
  enableMetricsTracking?: boolean;
  maxMetricsHistory?: number; // keep last N metric snapshots

  // Performance settings
  enableCompressionHints?: boolean;
  targetDataRate?: number; // KB/s
  adapativeQualityEnabled?: boolean;
}

// ============================================================================
// State Management
// ============================================================================

export class StreamingStateManager {
  private status: StreamingStatus;
  private config: StreamingConfig;
  private metrics: StreamingMetrics;
  private statusCallbacks: Array<(status: StreamingStatus) => void> = [];
  private metricsHistory: StreamingMetrics[] = [];
  private maxHistorySize = 100;
  private metricsInterval?: number;

  constructor(config: Partial<StreamingConfig> = {}) {
    this.config = {
      autoConnect: true,
      autoReconnect: true,
      maxReconnectAttempts: 10,
      initialReconnectDelayMs: 1000,
      backoffMultiplier: 2,
      bufferSize: 100,
      enableBuffering: true,
      highWaterMark: 80,
      lowWaterMark: 20,
      metricsUpdateIntervalMs: 1000,
      enableMetricsTracking: true,
      maxMetricsHistory: 100,
      ...config,
    };

    this.metrics = this.initializeMetrics();
    this.status = {
      isConnected: false,
      isStreaming: false,
      metrics: { ...this.metrics },
      lastUpdateTime: Date.now(),
    };

    if (this.config.enableMetricsTracking) {
      this.startMetricsTracking();
    }
  }

  private initializeMetrics(): StreamingMetrics {
    return {
      packetsReceived: 0,
      packetsDropped: 0,
      reconnects: 0,
      connectionTime: 0,
      latency: 0,
      jitter: 0,
      dataRate: 0,
      throughput: 0,
      bufferHealth: 1.0,
      bufferSize: 0,
      bufferMaxSize: this.config.bufferSize || 100,
      bufferUnderruns: 0,
      qualityLevel: 1.0,
      errorRate: 0,
      successRate: 100,
    };
  }

  // ========================================================================
  // Status Management
  // ========================================================================

  setConnected(connected: boolean, streaming: boolean = this.status.isStreaming): void {
    this.status = {
      ...this.status,
      isConnected: connected,
      isStreaming: streaming,
      connectionStartTime: connected ? Date.now() : undefined,
      lastUpdateTime: Date.now(),
    };

    if (connected && this.status.connectionStartTime) {
      this.metrics.connectionTime = Date.now() - this.status.connectionStartTime;
    }

    this.notifyStatusChange();
  }

  setStreaming(streaming: boolean): void {
    this.status.isStreaming = streaming;
    this.status.lastUpdateTime = Date.now();
    this.notifyStatusChange();
  }

  getStatus(): StreamingStatus {
    return {
      ...this.status,
      metrics: { ...this.metrics },
    };
  }

  // ========================================================================
  // Metrics Management
  // ========================================================================

  updateMetrics(updates: Partial<StreamingMetrics>): void {
    this.metrics = { ...this.metrics, ...updates };
    this.status.metrics = { ...this.metrics };
    this.status.lastUpdateTime = Date.now();

    // Store in history
    if (this.config.enableMetricsTracking) {
      this.metricsHistory.push({ ...this.metrics });
      if (this.metricsHistory.length > this.maxHistorySize) {
        this.metricsHistory.shift();
      }
    }
  }

  recordPacketReceived(): void {
    this.metrics.packetsReceived++;
    this.updateMetrics({ packetsReceived: this.metrics.packetsReceived });
  }

  recordPacketsDropped(count: number): void {
    this.metrics.packetsDropped += count;
    this.updateErrorRate();
    this.updateMetrics({ packetsDropped: this.metrics.packetsDropped });
  }

  recordReconnect(): void {
    this.metrics.reconnects++;
    this.updateMetrics({ reconnects: this.metrics.reconnects });
  }

  recordBufferUnderrun(): void {
    this.metrics.bufferUnderruns++;
    this.updateMetrics({ bufferUnderruns: this.metrics.bufferUnderruns });
  }

  updateLatency(latency: number): void {
    // Exponential moving average
    this.metrics.latency = this.metrics.latency * 0.9 + latency * 0.1;

    // Calculate jitter
    const jitter = Math.abs(latency - this.metrics.latency);
    this.metrics.jitter = this.metrics.jitter * 0.9 + jitter * 0.1;

    this.updateMetrics({
      latency: this.metrics.latency,
      jitter: this.metrics.jitter,
    });
  }

  updateBufferHealth(currentSize: number, maxSize: number): void {
    const health = Math.max(0, Math.min(1, currentSize / maxSize));
    this.metrics.bufferSize = currentSize;
    this.metrics.bufferMaxSize = maxSize;
    this.metrics.bufferHealth = health;

    this.updateMetrics({
      bufferHealth: health,
      bufferSize: currentSize,
      bufferMaxSize: maxSize,
    });
  }

  updateDataRate(bytesReceived: number, intervalMs: number): void {
    const dataRate = (bytesReceived * 1000) / (intervalMs * 1024); // KB/s
    const throughput = (bytesReceived * 1000) / intervalMs; // bytes/s

    this.metrics.dataRate = dataRate;
    this.metrics.throughput = throughput;

    this.updateMetrics({
      dataRate,
      throughput,
    });
  }

  updateQualityLevel(level: number): void {
    this.metrics.qualityLevel = Math.max(0, Math.min(1, level));
    this.updateMetrics({ qualityLevel: this.metrics.qualityLevel });
  }

  private updateErrorRate(): void {
    const total = this.metrics.packetsReceived + this.metrics.packetsDropped;
    if (total > 0) {
      this.metrics.errorRate = (this.metrics.packetsDropped / total) * 100;
      this.metrics.successRate = 100 - this.metrics.errorRate;
      this.updateMetrics({
        errorRate: this.metrics.errorRate,
        successRate: this.metrics.successRate,
      });
    }
  }

  getMetrics(): StreamingMetrics {
    return { ...this.metrics };
  }

  getMetricsHistory(): StreamingMetrics[] {
    return [...this.metricsHistory];
  }

  // ========================================================================
  // Configuration
  // ========================================================================

  updateConfig(updates: Partial<StreamingConfig>): void {
    this.config = { ...this.config, ...updates };
  }

  getConfig(): StreamingConfig {
    return { ...this.config };
  }

  // ========================================================================
  // Callbacks & Notifications
  // ========================================================================

  onStatusChange(callback: (status: StreamingStatus) => void): () => void {
    this.statusCallbacks.push(callback);
    return () => {
      const index = this.statusCallbacks.indexOf(callback);
      if (index > -1) {
        this.statusCallbacks.splice(index, 1);
      }
    };
  }

  private notifyStatusChange(): void {
    this.statusCallbacks.forEach(callback => {
      try {
        callback(this.getStatus());
      } catch (error) {
        console.error('Error in status callback:', error);
      }
    });
  }

  private startMetricsTracking(): void {
    if (this.metricsInterval) return;

    this.metricsInterval = window.setInterval(() => {
      // Metrics are already being updated; this just triggers periodic notifications
      this.notifyStatusChange();
    }, this.config.metricsUpdateIntervalMs || 1000);
  }

  // ========================================================================
  // Lifecycle
  // ========================================================================

  reset(): void {
    this.metrics = this.initializeMetrics();
    this.status = {
      isConnected: false,
      isStreaming: false,
      metrics: { ...this.metrics },
      lastUpdateTime: Date.now(),
    };
    this.metricsHistory = [];
  }

  cleanup(): void {
    if (this.metricsInterval) {
      clearInterval(this.metricsInterval);
      this.metricsInterval = undefined;
    }
    this.statusCallbacks = [];
    this.metricsHistory = [];
  }
}

// ============================================================================
// Callback Subscription System
// ============================================================================

export type StreamingEventCallback<T = any> = (data: T) => void;
export type StreamingErrorCallback = (error: Error, severity: 'low' | 'medium' | 'high') => void;

export class StreamingSubscriptionManager {
  private subscriptions: Map<string, Set<StreamingEventCallback>> = new Map();
  private errorSubscriptions: Set<StreamingErrorCallback> = new Set();

  subscribe<T = any>(event: string, callback: StreamingEventCallback<T>): () => void {
    if (!this.subscriptions.has(event)) {
      this.subscriptions.set(event, new Set());
    }

    const callbacks = this.subscriptions.get(event)!;
    callbacks.add(callback);

    // Return unsubscribe function
    return () => {
      callbacks.delete(callback);
      if (callbacks.size === 0) {
        this.subscriptions.delete(event);
      }
    };
  }

  emit<T = any>(event: string, data: T): void {
    const callbacks = this.subscriptions.get(event);
    if (!callbacks) return;

    callbacks.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`Error in ${event} callback:`, error);
      }
    });
  }

  onError(callback: StreamingErrorCallback): () => void {
    this.errorSubscriptions.add(callback);
    return () => {
      this.errorSubscriptions.delete(callback);
    };
  }

  emitError(error: Error, severity: 'low' | 'medium' | 'high' = 'high'): void {
    this.errorSubscriptions.forEach(callback => {
      try {
        callback(error, severity);
      } catch (err) {
        console.error('Error in error callback:', err);
      }
    });
  }

  clear(): void {
    this.subscriptions.clear();
    this.errorSubscriptions.clear();
  }
}

// ============================================================================
// Backpressure Management
// ============================================================================

export class BackpressureManager {
  private highWaterMark: number = 80;
  private lowWaterMark: number = 20;
  private isPaused = false;
  private onPause?: () => void;
  private onResume?: () => void;

  constructor(highWaterMark: number = 80, lowWaterMark: number = 20) {
    this.highWaterMark = highWaterMark;
    this.lowWaterMark = lowWaterMark;
  }

  checkBackpressure(bufferPercentage: number): boolean {
    if (!this.isPaused && bufferPercentage >= this.highWaterMark) {
      this.isPaused = true;
      this.onPause?.();
      return true; // Should pause
    }

    if (this.isPaused && bufferPercentage <= this.lowWaterMark) {
      this.isPaused = false;
      this.onResume?.();
      return false; // Should resume
    }

    return this.isPaused;
  }

  setCallbacks(onPause?: () => void, onResume?: () => void): void {
    this.onPause = onPause;
    this.onResume = onResume;
  }

  isPausedNow(): boolean {
    return this.isPaused;
  }

  reset(): void {
    this.isPaused = false;
  }
}

// ============================================================================
// Unified Streaming Factory
// ============================================================================

export function createStreamingState(config?: Partial<StreamingConfig>): StreamingStateManager {
  return new StreamingStateManager(config);
}

export function createSubscriptionManager(): StreamingSubscriptionManager {
  return new StreamingSubscriptionManager();
}

export function createBackpressureManager(
  highWaterMark: number = 80,
  lowWaterMark: number = 20
): BackpressureManager {
  return new BackpressureManager(highWaterMark, lowWaterMark);
}

export default {
  StreamingStateManager,
  StreamingSubscriptionManager,
  BackpressureManager,
  createStreamingState,
  createSubscriptionManager,
  createBackpressureManager,
};
