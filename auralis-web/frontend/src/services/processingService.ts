/**
 * Processing Service (Phase 3c)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Frontend service for audio processing operations.
 * Handles communication with the processing API backend.
 *
 * Enhanced with centralized error handling utilities:
 * - WebSocketManager for automatic reconnection
 * - Retry logic with exponential backoff
 * - Centralized error logging
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

import { WebSocketManager, retryWithBackoff, withErrorLogging } from '../utils/errorHandling';

export interface ProcessingSettings {
  mode: 'adaptive' | 'reference' | 'hybrid';
  output_format: 'wav' | 'flac' | 'mp3';
  bit_depth: 16 | 24 | 32;
  sample_rate?: number;

  // EQ settings
  eq?: {
    enabled: boolean;
    low: number;
    lowMid: number;
    mid: number;
    highMid: number;
    high: number;
  };

  // Dynamics settings
  dynamics?: {
    enabled: boolean;
    compressor: {
      threshold: number;
      ratio: number;
      attack: number;
      release: number;
    };
    limiter: {
      enabled: boolean;
      threshold: number;
      lookahead: number;
    };
  };

  // Level matching settings
  levelMatching?: {
    enabled: boolean;
    targetLufs: number;
    maxGain: number;
  };

  // Genre override
  genre_override?: string;
}

export interface ProcessingJob {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  error_message?: string;
  result_data?: {
    output_path: string;
    sample_rate: number;
    duration: number;
    format: string;
    bit_depth: number;
    processing_time?: number;
    genre_detected?: string;
    lufs?: number;
  };
}

export interface ProcessingPreset {
  name: string;
  description: string;
  mode: string;
  settings: Partial<ProcessingSettings>;
}

export interface QueueStatus {
  total_jobs: number;
  queued: number;
  processing: number;
  completed: number;
  failed: number;
  max_concurrent: number;
}

class ProcessingService {
  private baseUrl: string;
  private wsUrl: string;
  private wsManager: WebSocketManager | null = null;
  private jobCallbacks: Map<string, (job: ProcessingJob) => void> = new Map();

  constructor() {
    this.baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8765';
    this.wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8765/ws';
  }

  /**
   * Connect to WebSocket for real-time updates (Phase 3c: Uses WebSocketManager)
   */
  async connectWebSocket(): Promise<void> {
    if (this.wsManager?.isConnected()) {
      return;
    }

    this.wsManager = new WebSocketManager(this.wsUrl, {
      maxReconnectAttempts: 10,
      initialReconnectDelayMs: 1000,
      backoffMultiplier: 1.5,
      onReconnectAttempt: (attempt, delay) => {
        console.log(`[ProcessingService] Reconnecting... Attempt ${attempt}, waiting ${delay}ms`);
      },
    });

    // Setup message handler
    this.wsManager.on('message', (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);
        this.handleWebSocketMessage(message);
      } catch (error) {
        console.error('[ProcessingService] Failed to parse WebSocket message:', error);
      }
    });

    // Setup error handler
    this.wsManager.on('error', (event: Event) => {
      console.error('[ProcessingService] WebSocket error:', event);
    });

    // Setup close handler
    this.wsManager.on('close', () => {
      console.log('[ProcessingService] WebSocket disconnected (will auto-reconnect)');
    });

    await this.wsManager.connect();
    console.log('[ProcessingService] WebSocket connected');
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleWebSocketMessage(message: any) {
    if (message.type === 'job_progress') {
      const { job_id, progress, message: progressMessage } = message.data;

      // Update job status
      this.getJobStatus(job_id).then((job) => {
        const callback = this.jobCallbacks.get(job_id);
        if (callback) {
          callback(job);
        }
      });
    }
  }

  /**
   * Subscribe to job progress updates
   */
  subscribeToJob(jobId: string, callback: (job: ProcessingJob) => void) {
    this.jobCallbacks.set(jobId, callback);

    // Send subscription message if WebSocket is connected
    if (this.wsManager?.isConnected()) {
      this.wsManager.send(JSON.stringify({
        type: 'subscribe_job_progress',
        job_id: jobId
      }));
    }
  }

  /**
   * Unsubscribe from job progress updates
   */
  unsubscribeFromJob(jobId: string) {
    this.jobCallbacks.delete(jobId);
  }

  /**
   * Submit audio file for processing (Phase 3c: Retry logic added)
   */
  async processAudio(
    inputPath: string,
    settings: ProcessingSettings,
    referencePath?: string
  ): Promise<{ job_id: string; status: string; message: string }> {
    return await retryWithBackoff(async () => {
      const response = await fetch(`${this.baseUrl}/api/processing/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input_path: inputPath,
          settings,
          reference_path: referencePath,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to submit processing job');
      }

      return await response.json();
    }, {
      maxRetries: 3,
      initialDelayMs: 200,
    });
  }

  /**
   * Upload and process audio file in one request
   */
  async uploadAndProcess(
    file: File,
    settings: ProcessingSettings
  ): Promise<{ job_id: string; status: string; message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('settings', JSON.stringify(settings));

    const response = await fetch(`${this.baseUrl}/api/processing/upload-and-process`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to upload and process file');
    }

    return await response.json();
  }

  /**
   * Get processing job status (Phase 3c: Retry logic added)
   */
  async getJobStatus(jobId: string): Promise<ProcessingJob> {
    return await retryWithBackoff(async () => {
      const response = await fetch(`${this.baseUrl}/api/processing/job/${jobId}`);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get job status');
      }

      return await response.json();
    }, {
      maxRetries: 3,
      initialDelayMs: 100,
    });
  }

  /**
   * Download processed audio file (Phase 3c: Retry logic + timeout added)
   */
  async downloadResult(jobId: string): Promise<Blob> {
    return await retryWithBackoff(async () => {
      const response = await fetch(`${this.baseUrl}/api/processing/job/${jobId}/download`);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to download result');
      }

      return await response.blob();
    }, {
      maxRetries: 3,
      initialDelayMs: 500,
      maxDelayMs: 5000,
    });
  }

  /**
   * Get download URL for processed audio
   */
  getDownloadUrl(jobId: string): string {
    return `${this.baseUrl}/api/processing/job/${jobId}/download`;
  }

  /**
   * Cancel a processing job
   */
  async cancelJob(jobId: string): Promise<{ message: string; job_id: string }> {
    const response = await fetch(`${this.baseUrl}/api/processing/job/${jobId}/cancel`, {
      method: 'POST',
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to cancel job');
    }

    return await response.json();
  }

  /**
   * List all processing jobs
   */
  async listJobs(
    status?: string,
    limit: number = 50
  ): Promise<{ jobs: ProcessingJob[]; total: number }> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    params.append('limit', limit.toString());

    const response = await fetch(`${this.baseUrl}/api/processing/jobs?${params}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to list jobs');
    }

    return await response.json();
  }

  /**
   * Get processing queue status
   */
  async getQueueStatus(): Promise<QueueStatus> {
    const response = await fetch(`${this.baseUrl}/api/processing/queue/status`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get queue status');
    }

    return await response.json();
  }

  /**
   * Get available processing presets
   */
  async getPresets(): Promise<{ presets: Record<string, ProcessingPreset> }> {
    const response = await fetch(`${this.baseUrl}/api/processing/presets`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get presets');
    }

    return await response.json();
  }

  /**
   * Clean up old completed jobs
   */
  async cleanupOldJobs(maxAgeHours: number = 24): Promise<{ message: string }> {
    const response = await fetch(
      `${this.baseUrl}/api/processing/jobs/cleanup?max_age_hours=${maxAgeHours}`,
      {
        method: 'DELETE',
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to cleanup jobs');
    }

    return await response.json();
  }

  /**
   * Poll job status until completion
   */
  async waitForCompletion(
    jobId: string,
    onProgress?: (job: ProcessingJob) => void,
    pollInterval: number = 1000
  ): Promise<ProcessingJob> {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const job = await this.getJobStatus(jobId);

          if (onProgress) {
            onProgress(job);
          }

          if (job.status === 'completed') {
            resolve(job);
          } else if (job.status === 'failed' || job.status === 'cancelled') {
            reject(new Error(job.error_message || `Job ${job.status}`));
          } else {
            // Continue polling
            setTimeout(poll, pollInterval);
          }
        } catch (error) {
          reject(error);
        }
      };

      poll();
    });
  }
}

// Export singleton instance
export const processingService = new ProcessingService();

export default processingService;