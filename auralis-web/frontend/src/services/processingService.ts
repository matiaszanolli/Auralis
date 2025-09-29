/**
 * Processing Service
 * ~~~~~~~~~~~~~~~~~~
 *
 * Frontend service for audio processing operations.
 * Handles communication with the processing API backend.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

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
  private ws: WebSocket | null = null;
  private jobCallbacks: Map<string, (job: ProcessingJob) => void> = new Map();

  constructor() {
    this.baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    this.wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';
  }

  /**
   * Connect to WebSocket for real-time updates
   */
  connectWebSocket(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        console.log('[ProcessingService] WebSocket connected');
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error('[ProcessingService] WebSocket error:', error);
        reject(error);
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleWebSocketMessage(message);
        } catch (error) {
          console.error('[ProcessingService] Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onclose = () => {
        console.log('[ProcessingService] WebSocket disconnected');
        // Attempt to reconnect after 3 seconds
        setTimeout(() => this.connectWebSocket(), 3000);
      };
    });
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
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
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
   * Submit audio file for processing
   */
  async processAudio(
    inputPath: string,
    settings: ProcessingSettings,
    referencePath?: string
  ): Promise<{ job_id: string; status: string; message: string }> {
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
   * Get processing job status
   */
  async getJobStatus(jobId: string): Promise<ProcessingJob> {
    const response = await fetch(`${this.baseUrl}/api/processing/job/${jobId}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get job status');
    }

    return await response.json();
  }

  /**
   * Download processed audio file
   */
  async downloadResult(jobId: string): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/api/processing/job/${jobId}/download`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to download result');
    }

    return await response.blob();
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