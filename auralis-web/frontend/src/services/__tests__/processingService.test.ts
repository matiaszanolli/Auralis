/**
 * Tests for Processing Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the audio processing service API layer.
 * Mocks at the apiRequest and errorHandling module level.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../utils/apiRequest', () => ({
  get: vi.fn(),
  post: vi.fn(),
  del: vi.fn(),
  getBlob: vi.fn(),
}));

vi.mock('../../utils/errorHandling', () => ({
  WebSocketManager: vi.fn().mockImplementation(() => ({
    connect: vi.fn().mockResolvedValue(undefined),
    isConnected: vi.fn().mockReturnValue(false),
    on: vi.fn(),
    send: vi.fn(),
  })),
  retryWithBackoff: vi.fn((fn: () => Promise<any>) => fn()),
}));

vi.mock('../../config/api', () => ({
  getApiUrl: vi.fn((path: string) => `http://localhost:8765${path}`),
  WS_BASE_URL: 'ws://localhost:8765',
}));

import { get, post, del, getBlob } from '../../utils/apiRequest';
import { retryWithBackoff } from '../../utils/errorHandling';
import { processingService } from '../processingService';
import type { ProcessingSettings, ProcessingJob } from '../processingService';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;
const mockDel = del as ReturnType<typeof vi.fn>;
const mockGetBlob = getBlob as ReturnType<typeof vi.fn>;
const mockRetryWithBackoff = retryWithBackoff as ReturnType<typeof vi.fn>;

const defaultSettings: ProcessingSettings = {
  mode: 'adaptive',
  output_format: 'wav',
  bit_depth: 24,
};

const completedJob: ProcessingJob = {
  job_id: 'job-1',
  status: 'completed',
  progress: 100,
  result_data: {
    output_path: '/output/test.wav',
    sample_rate: 44100,
    duration: 120,
    format: 'wav',
    bit_depth: 24,
  },
};

const failedJob: ProcessingJob = {
  job_id: 'job-1',
  status: 'failed',
  progress: 50,
  error_message: 'Processing failed: invalid format',
};

describe('ProcessingService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // retryWithBackoff should just call the function by default
    mockRetryWithBackoff.mockImplementation((fn: () => Promise<any>) => fn());
  });

  describe('processAudio', () => {
    it('should call post with correct params', async () => {
      const response = { job_id: 'job-1', status: 'queued', message: 'Processing started' };
      mockPost.mockResolvedValueOnce(response);

      const result = await processingService.processAudio('/input/test.wav', defaultSettings, '/ref/ref.wav');

      expect(mockPost).toHaveBeenCalledWith('/api/processing/process', {
        input_path: '/input/test.wav',
        settings: defaultSettings,
        reference_path: '/ref/ref.wav',
      });
      expect(result).toEqual(response);
    });

    it('should propagate errors when post rejects', async () => {
      mockPost.mockRejectedValueOnce(new Error('Network error'));

      await expect(processingService.processAudio('/input/test.wav', defaultSettings)).rejects.toThrow(
        'Network error'
      );
    });
  });

  describe('getJobStatus', () => {
    it('should return job status with retry', async () => {
      mockGet.mockResolvedValueOnce(completedJob);

      const result = await processingService.getJobStatus('job-1');

      expect(mockRetryWithBackoff).toHaveBeenCalled();
      expect(mockGet).toHaveBeenCalledWith('/api/processing/job/job-1');
      expect(result).toEqual(completedJob);
    });
  });

  describe('waitForCompletion', () => {
    it('should resolve when job completes', async () => {
      mockGet.mockResolvedValueOnce(completedJob);

      const result = await processingService.waitForCompletion('job-1');

      expect(result).toEqual(completedJob);
    });

    it('should reject when job fails', async () => {
      mockGet.mockResolvedValueOnce(failedJob);

      await expect(processingService.waitForCompletion('job-1')).rejects.toThrow(
        'Processing failed: invalid format'
      );
    });

    it('should reject with default message for failed job without error_message', async () => {
      mockGet.mockResolvedValueOnce({ ...failedJob, error_message: undefined });

      await expect(processingService.waitForCompletion('job-1')).rejects.toThrow('Job failed');
    });

    it('should call onProgress callback', async () => {
      const processingJob: ProcessingJob = {
        job_id: 'job-1',
        status: 'processing',
        progress: 50,
      };
      mockGet.mockResolvedValueOnce(processingJob).mockResolvedValueOnce(completedJob);

      const onProgress = vi.fn();
      const result = await processingService.waitForCompletion('job-1', onProgress, 10);

      expect(onProgress).toHaveBeenCalledWith(processingJob);
      expect(onProgress).toHaveBeenCalledWith(completedJob);
      expect(result).toEqual(completedJob);
    });

    it('should reject immediately when signal is already aborted', async () => {
      const controller = new AbortController();
      controller.abort();

      await expect(
        processingService.waitForCompletion('job-1', undefined, 1000, controller.signal)
      ).rejects.toThrow('Polling aborted');
    });

    it('should reject when signal is aborted during polling', async () => {
      const controller = new AbortController();
      const processingJob: ProcessingJob = {
        job_id: 'job-1',
        status: 'processing',
        progress: 50,
      };
      mockGet.mockResolvedValue(processingJob);

      const promise = processingService.waitForCompletion('job-1', undefined, 50, controller.signal);

      // Abort after a short delay
      setTimeout(() => controller.abort(), 20);

      await expect(promise).rejects.toThrow('Polling aborted');
    });
  });

  describe('cancelJob', () => {
    it('should call post to cancel job', async () => {
      const response = { message: 'Job cancelled', job_id: 'job-1' };
      mockPost.mockResolvedValueOnce(response);

      const result = await processingService.cancelJob('job-1');

      expect(mockPost).toHaveBeenCalledWith('/api/processing/job/job-1/cancel');
      expect(result).toEqual(response);
    });
  });

  describe('downloadResult', () => {
    it('should download result blob with retry', async () => {
      const blob = new Blob(['audio-data'], { type: 'audio/wav' });
      mockGetBlob.mockResolvedValueOnce(blob);

      const result = await processingService.downloadResult('job-1');

      expect(mockRetryWithBackoff).toHaveBeenCalled();
      expect(mockGetBlob).toHaveBeenCalledWith('/api/processing/job/job-1/download');
      expect(result).toBe(blob);
    });
  });

  describe('listJobs', () => {
    it('should list jobs without status filter', async () => {
      const response = { jobs: [completedJob], total: 1 };
      mockGet.mockResolvedValueOnce(response);

      const result = await processingService.listJobs();

      expect(mockGet).toHaveBeenCalledWith('/api/processing/jobs?limit=50');
      expect(result).toEqual(response);
    });

    it('should list jobs with status filter', async () => {
      const response = { jobs: [completedJob], total: 1 };
      mockGet.mockResolvedValueOnce(response);

      const result = await processingService.listJobs('completed', 10);

      expect(mockGet).toHaveBeenCalledWith('/api/processing/jobs?status=completed&limit=10');
      expect(result).toEqual(response);
    });
  });

  describe('getDownloadUrl', () => {
    it('should return correct download URL', () => {
      const url = processingService.getDownloadUrl('job-1');

      expect(url).toBe('http://localhost:8765/api/processing/job/job-1/download');
    });
  });

  describe('subscribeToJob / unsubscribeFromJob', () => {
    it('should store callback in jobCallbacks map', () => {
      const callback = vi.fn();
      processingService.subscribeToJob('job-1', callback);

      // Verify the callback is stored (accessible via the private map)
      // We test indirectly: subscribing then unsubscribing should not throw
      expect(() => processingService.unsubscribeFromJob('job-1')).not.toThrow();
    });

    it('should remove callback on unsubscribe', () => {
      const callback = vi.fn();
      processingService.subscribeToJob('job-1', callback);
      processingService.unsubscribeFromJob('job-1');

      // Re-subscribing should work without issues
      processingService.subscribeToJob('job-1', callback);
      expect(() => processingService.unsubscribeFromJob('job-1')).not.toThrow();
    });

    it('should handle unsubscribe for non-existent job gracefully', () => {
      expect(() => processingService.unsubscribeFromJob('non-existent')).not.toThrow();
    });
  });

  describe('getQueueStatus', () => {
    it('should get queue status', async () => {
      const status = { total_jobs: 5, queued: 2, processing: 1, completed: 2, failed: 0, max_concurrent: 4 };
      mockGet.mockResolvedValueOnce(status);

      const result = await processingService.getQueueStatus();

      expect(mockGet).toHaveBeenCalledWith('/api/processing/queue/status');
      expect(result).toEqual(status);
    });
  });

  describe('getPresets', () => {
    it('should get processing presets', async () => {
      const presets = { presets: { default: { name: 'Default', description: 'Default preset', mode: 'adaptive', settings: {} } } };
      mockGet.mockResolvedValueOnce(presets);

      const result = await processingService.getPresets();

      expect(mockGet).toHaveBeenCalledWith('/api/processing/presets');
      expect(result).toEqual(presets);
    });
  });

  describe('cleanupOldJobs', () => {
    it('should call del with default max age', async () => {
      mockDel.mockResolvedValueOnce({ message: 'Cleaned up' });

      await processingService.cleanupOldJobs();

      expect(mockDel).toHaveBeenCalledWith('/api/processing/jobs/cleanup?max_age_hours=24');
    });

    it('should call del with custom max age', async () => {
      mockDel.mockResolvedValueOnce({ message: 'Cleaned up' });

      await processingService.cleanupOldJobs(48);

      expect(mockDel).toHaveBeenCalledWith('/api/processing/jobs/cleanup?max_age_hours=48');
    });
  });
});
