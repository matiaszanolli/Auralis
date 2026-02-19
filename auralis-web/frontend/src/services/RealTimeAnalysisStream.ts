/**
 * Real-Time Analysis Stream for Phase 5.3 (Phase 3c Enhanced, Phase 5d Refactored)
 *
 * This service provides real-time streaming of audio analysis data from the
 * Phase 5.1 backend to Phase 5.2 visualization components with buffering,
 * interpolation, and error recovery.
 *
 * Phase 5d: Refactored to use unified streaming infrastructure
 * - StreamingStateManager for state and metrics management
 * - StreamingSubscriptionManager for callback handling
 * - Eliminated duplicate metrics tracking code (moved to infrastructure)
 *
 * Enhanced with centralized error handling (Phase 3c):
 * - WebSocketManager for automatic reconnection
 * - Centralized error classification
 */

import { WebSocketManager, classifyErrorSeverity } from '../utils/errorHandling';
import {
  StreamingStateManager,
  StreamingSubscriptionManager,
  BackpressureManager,
  createStreamingState,
  createSubscriptionManager,
  createBackpressureManager,
} from '../utils/streamingInfrastructure';

interface AudioStreamConfig {
  sampleRate: number;
  channels: number;
  bufferSize: number;
  analysisInterval: number; // ms
  maxLatency: number; // ms
  enableInterpolation: boolean;
  enableBuffering: boolean;
}

interface AnalysisStreamData {
  timestamp: number;
  sequence: number;

  // Phase 5.1 Analysis Data
  spectrum?: {
    frequency_bins: number[];
    magnitude_db: number[];
    peak_frequency: number;
    spectral_centroid: number;
    spectral_rolloff?: number;
    settings?: any;
  };

  loudness?: {
    momentary_loudness: number;
    short_term_loudness: number;
    integrated_loudness: number;
    loudness_range: number;
    peak_dbfs: number;
    true_peak_dbfs: number;
  };

  correlation?: {
    correlation_coefficient: number;
    phase_correlation: number;
    stereo_width: number;
    mono_compatibility: number;
    phase_stability: number;
    phase_deviation: number;
    stereo_position: number;
    left_energy: number;
    right_energy: number;
  };

  dynamics?: {
    dr_value: number;
    peak_to_loudness_ratio: number;
    crest_factor: number;
    compression_ratio: number;
    attack_time: number;
    release_time: number;
    loudness_war_assessment: any;
  };

  // Real-time audio data
  waveform?: {
    peaks: number[];
    rms: number[];
    duration: number;
  };

  // Processing metrics
  processing?: {
    stages: Array<{
      name: string;
      isActive: boolean;
      cpuUsage: number;
      latency: number;
      bufferUsage: number;
      inputLevel: number;
      outputLevel: number;
      gainReduction: number;
      parameters: { [key: string]: number };
      alerts: string[];
    }>;
    globalCpuUsage: number;
    globalLatency: number;
    bufferUnderruns: number;
    isRealTime: boolean;
    processingLoad: number;
  };
}

interface StreamMetrics {
  packetsReceived: number;
  packetsDropped: number;
  latency: number;
  jitter: number;
  bufferHealth: number;
  reconnects: number;
  dataRate: number; // KB/s
}

type AnalysisDataCallback = (data: AnalysisStreamData) => void;
type StreamStatusCallback = (connected: boolean, metrics: StreamMetrics) => void;
type ErrorCallback = (error: Error, severity: 'low' | 'medium' | 'high') => void;

export class RealTimeAnalysisStream {
  private config: AudioStreamConfig;
  private wsManager: WebSocketManager | null = null;

  // Unified streaming infrastructure (Phase 5d)
  private stateManager: StreamingStateManager;
  private subscriptions: StreamingSubscriptionManager;
  private backpressure: BackpressureManager;

  // Data buffers
  private dataBuffer: AnalysisStreamData[] = [];
  private lastReceivedSequence = -1;

  // Interpolation
  private interpolationBuffer: Map<string, number[]> = new Map();
  private interpolationHistory = 10;

  // Legacy callbacks (for backward compatibility)
  private dataCallbacks: AnalysisDataCallback[] = [];
  private statusCallbacks: StreamStatusCallback[] = [];
  private errorCallbacks: ErrorCallback[] = [];

  // Timers
  private bufferProcessingInterval?: number;
  private heartbeatInterval?: number;

  // State tracking
  private isConnected: boolean = false;

  constructor(config: Partial<AudioStreamConfig> = {}) {
    this.config = {
      sampleRate: 44100,
      channels: 2,
      bufferSize: 512,
      analysisInterval: 50, // 20Hz update rate
      maxLatency: 100, // 100ms max latency
      enableInterpolation: true,
      enableBuffering: true,
      ...config,
    };

    // Initialize unified streaming infrastructure (Phase 5d)
    this.stateManager = createStreamingState({
      bufferSize: this.config.bufferSize,
      enableBuffering: this.config.enableBuffering,
      metricsUpdateIntervalMs: this.config.analysisInterval,
    });

    this.subscriptions = createSubscriptionManager();
    this.backpressure = createBackpressureManager(80, 20);

    // Wire status change listener for backward compatibility
    this.stateManager.onStatusChange(() => {
      this.notifyStatusChange();
    });

    this.startBufferProcessing();
  }

  // Connection Management (Phase 3c: Uses WebSocketManager)
  async connect(endpoint: string = 'ws://localhost:8080/analysis-stream'): Promise<void> {
    try {
      this.wsManager = new WebSocketManager(endpoint, {
        maxReconnectAttempts: 10,
        initialReconnectDelayMs: 1000,
        backoffMultiplier: 2,
        onReconnectAttempt: (attempt, delay) => {
          console.log(`🔄 Reconnection attempt ${attempt}/10 (waiting ${delay}ms)`);
        },
      });

      // Setup message handler
      this.wsManager.on('message', ((event: MessageEvent | Event) => {
        this.handleMessage(event as MessageEvent);
      }) as (event: MessageEvent | Event) => void);

      // Setup error handler
      this.wsManager.on('error', (event: Event) => {
        this.handleError(event);
      });

      // Setup close handler
      this.wsManager.on('close', () => {
        this.handleClose();
      });

      // Setup open handler
      this.wsManager.on('open', () => {
        this.handleOpen();
      });

      await this.wsManager.connect();
    } catch (error) {
      this.handleConnectionError(error as Error);
    }
  }

  disconnect(): void {
    this.stateManager.setStreaming(false);

    if (this.wsManager) {
      this.wsManager.close();
      this.wsManager = null;
    }

    this.clearTimers();
  }

  private handleOpen(): void {
    console.log('🎵 Analysis stream connected');

    // Update state tracking
    this.isConnected = true;

    // Update state using state manager (Phase 5d)
    this.stateManager.setConnected(true, false);

    // Send configuration
    this.sendConfiguration();

    // Start heartbeat
    this.startHeartbeat();

    this.notifyStatusChange();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const data: AnalysisStreamData = JSON.parse(event.data);

      // Update metrics using state manager (Phase 5d)
      this.stateManager.recordPacketReceived();
      this.stateManager.updateLatency(Date.now() - data.timestamp);

      // Check sequence for dropped packets
      if (this.lastReceivedSequence >= 0 && data.sequence !== this.lastReceivedSequence + 1) {
        const dropped = data.sequence - this.lastReceivedSequence - 1;
        this.stateManager.recordPacketsDropped(dropped);
        this.handleDroppedPackets(dropped);
      }
      this.lastReceivedSequence = data.sequence;

      // Check backpressure (Phase 5d)
      const bufferPercentage = (this.dataBuffer.length / this.config.bufferSize) * 100;
      this.backpressure.checkBackpressure(bufferPercentage);

      // Process data
      this.processIncomingData(data);

    } catch (error) {
      this.handleParseError(new Error(`Failed to parse stream data: ${error}`));
    }
  }

  private handleClose(): void {
    console.log('🔌 Analysis stream disconnected (will auto-reconnect)');
    this.isConnected = false;
    this.stateManager.setConnected(false, false);
    this.clearTimers();
    // WebSocketManager handles reconnection automatically
    this.notifyStatusChange();
  }

  private handleError(error: Event): void {
    console.error('🚨 WebSocket error:', error);
    const err = new Error('WebSocket connection error');
    // Use centralized error classification (Phase 3c)
    const severity = classifyErrorSeverity(err);
    this.handleConnectionError(err, severity);
  }

  private handleParseError(error: Error): void {
    console.error('Failed to parse WebSocket message:', error);
    // Use centralized error classification (Phase 3c)
    const severity = classifyErrorSeverity(error);
    this.handleConnectionError(error, severity);
  }

  private handleConnectionError(error: Error, severity: 'low' | 'medium' | 'high' | 'critical' = 'high'): void {
    // Map critical severity to high for backward compatibility with ErrorCallback
    const callbackSeverity = severity === 'critical' ? 'high' : severity;
    this.errorCallbacks.forEach(callback => {
      callback(error, callbackSeverity as 'low' | 'medium' | 'high');
    });
  }

  private handleDroppedPackets(count: number): void {
    console.warn(`📦 Dropped ${count} packets - Buffer health: ${this.metrics.bufferHealth}`);

    if (count > 5) {
      this.errorCallbacks.forEach(callback => {
        callback(new Error(`High packet loss: ${count} packets dropped`), 'medium');
      });
    }
  }

  // Configuration
  private sendConfiguration(): void {
    if (this.wsManager?.isConnected()) {
      const configMessage = {
        type: 'configure',
        config: this.config,
        timestamp: Date.now(),
      };

      this.wsManager.send(JSON.stringify(configMessage));
    }
  }

  updateConfiguration(newConfig: Partial<AudioStreamConfig>): void {
    this.config = { ...this.config, ...newConfig };
    this.sendConfiguration();
  }

  // Data Processing
  private processIncomingData(data: AnalysisStreamData): void {
    // Add to buffer if buffering is enabled
    if (this.config.enableBuffering) {
      this.addToBuffer(data);
    } else {
      // Direct processing
      this.processData(data);
    }

    // Update interpolation data
    if (this.config.enableInterpolation) {
      this.updateInterpolationData(data);
    }
  }

  private addToBuffer(data: AnalysisStreamData): void {
    this.dataBuffer.push(data);

    // Maintain buffer size
    if (this.dataBuffer.length > this.config.bufferSize) {
      this.dataBuffer.shift();
    }

    // Update buffer health using state manager (Phase 5d)
    this.stateManager.updateBufferHealth(this.dataBuffer.length, this.config.bufferSize);
  }

  private processData(data: AnalysisStreamData): void {
    // Apply interpolation if needed
    const processedData = this.config.enableInterpolation ?
      this.interpolateData(data) : data;

    // Notify subscribers
    this.dataCallbacks.forEach(callback => {
      try {
        callback(processedData);
      } catch (error) {
        console.error('Error in data callback:', error);
      }
    });
  }

  // Interpolation
  private updateInterpolationData(data: AnalysisStreamData): void {
    // Store key metrics for interpolation
    const metrics: [string, number | undefined][] = [
      ['spectrum_peak', data.spectrum?.peak_frequency],
      ['loudness_momentary', data.loudness?.momentary_loudness],
      ['correlation', data.correlation?.correlation_coefficient],
      ['dynamics_dr', data.dynamics?.dr_value],
    ];

    metrics.forEach(([key, value]) => {
      if (typeof value === 'number') {
        if (!this.interpolationBuffer.has(key)) {
          this.interpolationBuffer.set(key, []);
        }

        const buffer = this.interpolationBuffer.get(key)!;
        buffer.push(value);

        if (buffer.length > this.interpolationHistory) {
          buffer.shift();
        }
      }
    });
  }

  private interpolateData(data: AnalysisStreamData): AnalysisStreamData {
    // Simple linear interpolation for smooth visualization
    const interpolated = { ...data };

    if (data.spectrum && this.interpolationBuffer.has('spectrum_peak')) {
      const history = this.interpolationBuffer.get('spectrum_peak')!;
      if (history.length > 1) {
        const smoothed = this.smoothValue(data.spectrum.peak_frequency, history);
        interpolated.spectrum = { ...data.spectrum, peak_frequency: smoothed };
      }
    }

    if (data.loudness && this.interpolationBuffer.has('loudness_momentary')) {
      const history = this.interpolationBuffer.get('loudness_momentary')!;
      if (history.length > 1) {
        const smoothed = this.smoothValue(data.loudness.momentary_loudness, history);
        interpolated.loudness = { ...data.loudness, momentary_loudness: smoothed };
      }
    }

    return interpolated;
  }

  private smoothValue(current: number, history: number[]): number {
    // Exponential moving average
    const alpha = 0.3; // Smoothing factor
    const avg = history.reduce((sum, val) => sum + val, 0) / history.length;
    return current * alpha + avg * (1 - alpha);
  }

  // Buffer Processing
  private startBufferProcessing(): void {
    this.bufferProcessingInterval = window.setInterval(() => {
      if (this.config.enableBuffering && this.dataBuffer.length > 0) {
        // Process oldest data in buffer
        const data = this.dataBuffer.shift();
        if (data) {
          this.processData(data);
        }
      }
    }, this.config.analysisInterval);
  }

  // Heartbeat (metrics monitoring is now handled by StreamingStateManager)
  private startHeartbeat(): void {
    this.heartbeatInterval = window.setInterval(() => {
      if (this.wsManager?.isConnected()) {
        this.wsManager.send(JSON.stringify({
          type: 'heartbeat',
          timestamp: Date.now(),
        }));
      }
    }, 30000); // 30 second heartbeat
  }

  private clearTimers(): void {
    // metricsInterval is now handled by StateManager (Phase 5d)
    if (this.bufferProcessingInterval) clearInterval(this.bufferProcessingInterval);
    if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
  }

  private notifyStatusChange(): void {
    this.statusCallbacks.forEach(callback => {
      try {
        callback(this.isConnected, { ...this.metrics });
      } catch (error) {
        console.error('Error in status callback:', error);
      }
    });
  }

  // Public API
  onData(callback: AnalysisDataCallback): () => void {
    this.dataCallbacks.push(callback);
    return () => {
      const index = this.dataCallbacks.indexOf(callback);
      if (index > -1) {
        this.dataCallbacks.splice(index, 1);
      }
    };
  }

  onStatusChange(callback: StreamStatusCallback): () => void {
    this.statusCallbacks.push(callback);
    return () => {
      const index = this.statusCallbacks.indexOf(callback);
      if (index > -1) {
        this.statusCallbacks.splice(index, 1);
      }
    };
  }

  onError(callback: ErrorCallback): () => void {
    this.errorCallbacks.push(callback);
    return () => {
      const index = this.errorCallbacks.indexOf(callback);
      if (index > -1) {
        this.errorCallbacks.splice(index, 1);
      }
    };
  }

  get metrics(): StreamMetrics {
    return this.getMetrics();
  }

  getMetrics(): StreamMetrics {
    // Return metrics from state manager (Phase 5d)
    const unified = this.stateManager.getMetrics();
    return {
      packetsReceived: unified.packetsReceived,
      packetsDropped: unified.packetsDropped,
      latency: unified.latency,
      jitter: unified.jitter,
      bufferHealth: unified.bufferHealth,
      reconnects: unified.reconnects,
      dataRate: unified.dataRate,
    };
  }

  isStreamingData(): boolean {
    return this.stateManager.getStatus().isConnected && this.stateManager.getStatus().isStreaming;
  }

  getBufferStatus(): { size: number; health: number; maxSize: number } {
    const metrics = this.stateManager.getMetrics();
    return {
      size: this.dataBuffer.length,
      health: metrics.bufferHealth,
      maxSize: this.config.bufferSize,
    };
  }

  // Control Methods
  startStreaming(): void {
    this.stateManager.setStreaming(true);
    if (this.wsManager?.isConnected()) {
      this.wsManager.send(JSON.stringify({
        type: 'start_stream',
        timestamp: Date.now(),
      }));
    }
  }

  stopStreaming(): void {
    this.stateManager.setStreaming(false);
    if (this.wsManager?.isConnected()) {
      this.wsManager.send(JSON.stringify({
        type: 'stop_stream',
        timestamp: Date.now(),
      }));
    }
  }

  // Cleanup
  destroy(): void {
    this.disconnect();
    this.dataCallbacks = [];
    this.statusCallbacks = [];
    this.errorCallbacks = [];
    this.dataBuffer = [];
    this.interpolationBuffer.clear();

    // Cleanup unified streaming infrastructure (Phase 5d)
    this.stateManager.cleanup();
    this.subscriptions.clear();
  }
}

// React Hook for Real-Time Analysis Stream
export function useRealTimeAnalysisStream(
  endpoint?: string,
  config?: Partial<AudioStreamConfig>
) {
  const [stream] = React.useState(() => new RealTimeAnalysisStream(config));
  const [isConnected, setIsConnected] = React.useState(false);
  const [metrics, setMetrics] = React.useState<StreamMetrics>(stream.getMetrics());
  const [lastData, setLastData] = React.useState<AnalysisStreamData | null>(null);
  const [error, setError] = React.useState<Error | null>(null);

  React.useEffect(() => {
    // Connect to stream
    if (endpoint) {
      stream.connect(endpoint).catch(setError);
    }

    // Set up callbacks
    const unsubscribeData = stream.onData(setLastData);
    const unsubscribeStatus = stream.onStatusChange((connected, streamMetrics) => {
      setIsConnected(connected);
      setMetrics(streamMetrics);
    });
    const unsubscribeError = stream.onError(setError);

    // Start streaming
    stream.startStreaming();

    return () => {
      unsubscribeData();
      unsubscribeStatus();
      unsubscribeError();
      stream.destroy();
    };
  }, [stream, endpoint]);

  return {
    stream,
    isConnected,
    metrics,
    lastData,
    error,
    startStreaming: () => stream.startStreaming(),
    stopStreaming: () => stream.stopStreaming(),
    getBufferStatus: () => stream.getBufferStatus(),
  };
}

// Import React for the hook
import React from 'react';

export default RealTimeAnalysisStream;