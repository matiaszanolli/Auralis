/**
 * Real-Time Analysis Stream for Phase 5.3 (Phase 3c Enhanced)
 *
 * This service provides real-time streaming of audio analysis data from the
 * Phase 5.1 backend to Phase 5.2 visualization components with buffering,
 * interpolation, and error recovery.
 *
 * Enhanced with centralized error handling (Phase 3c):
 * - WebSocketManager for automatic reconnection
 * - Centralized error classification
 */

import { WebSocketManager, classifyErrorSeverity } from '../utils/errorHandling';

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
  private isConnected = false;
  private isStreaming = false;
  private wsManager: WebSocketManager | null = null;
  private currentEndpoint: string = '';

  // Data buffers
  private dataBuffer: AnalysisStreamData[] = [];
  private maxBufferSize = 100;
  private sequenceNumber = 0;
  private lastReceivedSequence = -1;

  // Interpolation
  private interpolationBuffer: Map<string, number[]> = new Map();
  private interpolationHistory = 10;

  // Callbacks
  private dataCallbacks: AnalysisDataCallback[] = [];
  private statusCallbacks: StreamStatusCallback[] = [];
  private errorCallbacks: ErrorCallback[] = [];

  // Metrics
  private metrics: StreamMetrics = {
    packetsReceived: 0,
    packetsDropped: 0,
    latency: 0,
    jitter: 0,
    bufferHealth: 1.0,
    reconnects: 0,
    dataRate: 0,
  };

  // Timers
  private metricsInterval?: number;
  private bufferProcessingInterval?: number;
  private heartbeatInterval?: number;

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

    this.startMetricsMonitoring();
    this.startBufferProcessing();
  }

  // Connection Management (Phase 3c: Uses WebSocketManager)
  async connect(endpoint: string = 'ws://localhost:8080/analysis-stream'): Promise<void> {
    this.currentEndpoint = endpoint;

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
      this.wsManager.on('message', (event: MessageEvent) => {
        this.handleMessage(event);
      });

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
    this.isStreaming = false;

    if (this.wsManager) {
      this.wsManager.close();
      this.wsManager = null;
    }

    this.clearTimers();
  }

  private handleOpen(): void {
    console.log('🎵 Analysis stream connected');
    this.isConnected = true;

    // Send configuration
    this.sendConfiguration();

    // Start heartbeat
    this.startHeartbeat();

    this.notifyStatusChange();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const data: AnalysisStreamData = JSON.parse(event.data);

      // Update metrics
      this.metrics.packetsReceived++;
      this.updateLatencyMetrics(data.timestamp);

      // Check sequence for dropped packets
      if (this.lastReceivedSequence >= 0 && data.sequence !== this.lastReceivedSequence + 1) {
        const dropped = data.sequence - this.lastReceivedSequence - 1;
        this.metrics.packetsDropped += dropped;
        this.handleDroppedPackets(dropped);
      }
      this.lastReceivedSequence = data.sequence;

      // Process data
      this.processIncomingData(data);

    } catch (error) {
      this.handleError(new Error(`Failed to parse stream data: ${error}`));
    }
  }

  private handleClose(): void {
    console.log('🔌 Analysis stream disconnected (will auto-reconnect)');
    this.isConnected = false;
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

  private handleConnectionError(error: Error, severity: 'low' | 'medium' | 'high' = 'high'): void {
    this.errorCallbacks.forEach(callback => {
      callback(error, severity);
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
    if (this.dataBuffer.length > this.maxBufferSize) {
      this.dataBuffer.shift();
    }

    // Update buffer health
    this.metrics.bufferHealth = Math.max(0, 1 - (this.dataBuffer.length / this.maxBufferSize));
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
    const metrics = [
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

  // Metrics and Monitoring
  private startMetricsMonitoring(): void {
    this.metricsInterval = window.setInterval(() => {
      this.updateMetrics();
      this.notifyStatusChange();
    }, 1000);
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = window.setInterval(() => {
      if (this.websocket?.readyState === WebSocket.OPEN) {
        this.websocket.send(JSON.stringify({
          type: 'heartbeat',
          timestamp: Date.now(),
        }));
      }
    }, 30000); // 30 second heartbeat
  }

  private updateLatencyMetrics(packetTimestamp: number): void {
    const now = Date.now();
    const latency = now - packetTimestamp;

    // Update latency with exponential moving average
    this.metrics.latency = this.metrics.latency * 0.9 + latency * 0.1;

    // Calculate jitter (latency variation)
    const jitter = Math.abs(latency - this.metrics.latency);
    this.metrics.jitter = this.metrics.jitter * 0.9 + jitter * 0.1;
  }

  private updateMetrics(): void {
    // Calculate data rate
    const dataRate = (this.metrics.packetsReceived * 1024) / 1000; // Rough estimate
    this.metrics.dataRate = dataRate;

    // Reset counters periodically
    if (this.metrics.packetsReceived > 1000) {
      this.metrics.packetsReceived = Math.floor(this.metrics.packetsReceived * 0.9);
      this.metrics.packetsDropped = Math.floor(this.metrics.packetsDropped * 0.9);
    }
  }

  private clearTimers(): void {
    if (this.metricsInterval) clearInterval(this.metricsInterval);
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

  getMetrics(): StreamMetrics {
    return { ...this.metrics };
  }

  isStreamingData(): boolean {
    return this.isConnected && this.isStreaming;
  }

  getBufferStatus(): { size: number; health: number; maxSize: number } {
    return {
      size: this.dataBuffer.length,
      health: this.metrics.bufferHealth,
      maxSize: this.maxBufferSize,
    };
  }

  // Control Methods
  startStreaming(): void {
    this.isStreaming = true;
    if (this.websocket?.readyState === WebSocket.OPEN) {
      this.websocket.send(JSON.stringify({
        type: 'start_stream',
        timestamp: Date.now(),
      }));
    }
  }

  stopStreaming(): void {
    this.isStreaming = false;
    if (this.websocket?.readyState === WebSocket.OPEN) {
      this.websocket.send(JSON.stringify({
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