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
import { get, post, del, getBlob } from '../utils/apiRequest';
import { getApiUrl, WS_BASE_URL } from '../config/api';

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
  // baseUrl removed — HTTP calls use centralized getApiUrl() (fixes #2466)
  private wsUrl: string;
  private wsManager: WebSocketManager | null = null;
  private jobCallbacks: Map<string, (job: ProcessingJob) => void> = new Map();

  constructor() {
    this.wsUrl = import.meta.env.VITE_WS_URL || `${WS_BASE_URL}/ws`;
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
    this.wsManager.on('message', ((event: MessageEvent | Event) => {
      try {
        const messageEvent = event as MessageEvent;
        const message = JSON.parse(messageEvent.data);
        this.handleWebSocketMessage(message);
      } catch (error) {
        console.error('[ProcessingService] Failed to parse WebSocket message:', error);
      }
    }) as (event: MessageEvent | Event) => void);

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
   * Handle incoming WebSocket messages (#2549)
   * Parameter typed as `unknown`; narrowed with a type guard before access.
   */
  private handleWebSocketMessage(message: unknown): void {
    if (
      typeof message === 'object' &&
      message !== null &&
      'type' in message &&
      (message as { type: unknown }).type === 'job_progress' &&
      'data' in message
    ) {
      const data = (message as { type: string; data: { job_id: string } }).data;
      const { job_id } = data;

      // Update job status via callback
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
    return await retryWithBackoff(
      () => post('/api/processing/process', {
        input_path: inputPath,
        settings,
        reference_path: referencePath,
      }),
      { maxRetries: 3, initialDelayMs: 200 }
    );
  }

  /**
   * Upload and process audio file in one request
   */
  async uploadAndProcess(
    file: File,
    settings: ProcessingSettings
  ): Promise<{ job_id: string; status: string; message: string }> {
    // Multipart FormData upload — not supported by the JSON-only apiRequest utility,
    // so we use getApiUrl() for the URL while still routing through fetch directly.
    const formData = new FormData();
    formData.append('file', file);
    formData.append('settings', JSON.stringify(settings));

    const response = await fetch(getApiUrl('/api/processing/upload-and-process'), {
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
    return await retryWithBackoff(
      () => get<ProcessingJob>(`/api/processing/job/${jobId}`),
      { maxRetries: 3, initialDelayMs: 100 }
    );
  }

  /**
   * Download processed audio file (Phase 3c: Retry logic + timeout added)
   */
  async downloadResult(jobId: string): Promise<Blob> {
    return await retryWithBackoff(
      () => getBlob(`/api/processing/job/${jobId}/download`),
      { maxRetries: 3, initialDelayMs: 500, maxDelayMs: 5000 }
    );
  }

  /**
   * Get download URL for processed audio
   */
  getDownloadUrl(jobId: string): string {
    return getApiUrl(`/api/processing/job/${jobId}/download`);
  }

  /**
   * Cancel a processing job
   */
  async cancelJob(jobId: string): Promise<{ message: string; job_id: string }> {
    return post(`/api/processing/job/${jobId}/cancel`);
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
    return get(`/api/processing/jobs?${params}`);
  }

  /**
   * Get processing queue status
   */
  async getQueueStatus(): Promise<QueueStatus> {
    return get('/api/processing/queue/status');
  }

  /**
   * Get available processing presets
   */
  async getPresets(): Promise<{ presets: Record<string, ProcessingPreset> }> {
    return get('/api/processing/presets');
  }

  /**
   * Clean up old completed jobs
   */
  async cleanupOldJobs(maxAgeHours: number = 24): Promise<{ message: string }> {
    return del(`/api/processing/jobs/cleanup?max_age_hours=${maxAgeHours}`);
  }

  /**
   * Poll job status until completion.
   *
   * Pass an AbortSignal to cancel polling on component unmount (fixes #2358).
   * The returned promise rejects with an AbortError when the signal fires.
   */
  async waitForCompletion(
    jobId: string,
    onProgress?: (job: ProcessingJob) => void,
    pollInterval: number = 1000,
    signal?: AbortSignal
  ): Promise<ProcessingJob> {
    return new Promise((resolve, reject) => {
      let timerId: ReturnType<typeof setTimeout> | undefined;

      const cleanup = () => {
        if (timerId !== undefined) {
          clearTimeout(timerId);
          timerId = undefined;
        }
      };

      if (signal) {
        if (signal.aborted) {
          reject(new DOMException('Polling aborted', 'AbortError'));
          return;
        }
        signal.addEventListener('abort', () => {
          cleanup();
          reject(new DOMException('Polling aborted', 'AbortError'));
        }, { once: true });
      }

      const poll = async () => {
        if (signal?.aborted) return;
        try {
          const job = await this.getJobStatus(jobId);

          if (onProgress) {
            onProgress(job);
          }

          if (job.status === 'completed') {
            cleanup();
            resolve(job);
          } else if (job.status === 'failed' || job.status === 'cancelled') {
            cleanup();
            reject(new Error(job.error_message || `Job ${job.status}`));
          } else {
            // Continue polling
            timerId = setTimeout(poll, pollInterval);
          }
        } catch (error) {
          cleanup();
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