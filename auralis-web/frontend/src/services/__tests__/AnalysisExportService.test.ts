/**
 * Tests for Analysis Export Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the analysis session management and export functionality.
 * Mocks export infrastructure utilities and error handling.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockProgressTracker = {
  updateProgress: vi.fn(),
  subscribe: vi.fn().mockReturnValue(vi.fn()),
  clear: vi.fn(),
};

vi.mock('../../utils/exportInfrastructure', () => ({
  calculateRunningAverage: vi.fn(
    (currentAvg: number, newValue: number, count: number) =>
      currentAvg + (newValue - currentAvg) / count
  ),
  extractNumericValues: vi.fn(
    (items: any[], extractor: (item: any) => number | undefined) =>
      items.map(extractor).filter((v: any) => v !== undefined && v !== null) as number[]
  ),
  calculateStatistics: vi.fn((values: number[]) => {
    const sum = values.reduce((a, b) => a + b, 0);
    return {
      average: sum / values.length,
      min: Math.min(...values),
      max: Math.max(...values),
      stdDev: 0,
      median: values[Math.floor(values.length / 2)],
      count: values.length,
    };
  }),
  ProgressTracker: vi.fn(() => mockProgressTracker),
  CanvasRenderingUtils: {
    setBackground: vi.fn(),
    getThemeColors: vi.fn().mockReturnValue({ text: '#fff', bg: '#000' }),
  },
  DataTransformer: {
    escapeXml: vi.fn((s: string) => s),
  },
}));

vi.mock('../../utils/errorHandling', () => ({
  createTimeoutPromise: vi.fn((promise: Promise<any>) => promise),
  globalErrorLogger: {
    log: vi.fn(),
  },
}));

vi.mock('../../design-system', () => ({
  tokens: {
    colors: {
      audioSemantic: { spatial: '#00f', transient: '#f80' },
      semantic: { info: '#08f', warning: '#fa0', error: '#f00' },
      text: { primaryFull: '#fff' },
      bg: { level0: '#000', level2: '#333' },
    },
  },
}));

// Provide navigator.userAgent and window.crypto for the service
Object.defineProperty(globalThis, 'navigator', {
  value: { userAgent: 'test-agent' },
  writable: true,
});

if (!globalThis.window) {
  (globalThis as any).window = {};
}
if (!(globalThis.window as any).crypto) {
  (globalThis.window as any).crypto = {
    getRandomValues: (arr: Uint32Array) => {
      for (let i = 0; i < arr.length; i++) arr[i] = Math.floor(Math.random() * 0xffffffff);
      return arr;
    },
  };
}
if (!(globalThis.window as any).msCrypto) {
  (globalThis.window as any).msCrypto = (globalThis.window as any).crypto;
}

import { AnalysisExportService } from '../AnalysisExportService';

function createService(): AnalysisExportService {
  return new AnalysisExportService();
}

describe('AnalysisExportService', () => {
  let service: AnalysisExportService;

  beforeEach(() => {
    vi.clearAllMocks();
    service = createService();
  });

  describe('startNewSession', () => {
    it('should initialize a session with default metadata', () => {
      const sessionId = service.startNewSession();

      expect(sessionId).toMatch(/^auralis_session_\d+_/);
      const session = service.getCurrentSession();
      expect(session).not.toBeNull();
      expect(session!.metadata.version).toBe('5.3.0');
      expect(session!.metadata.sampleRate).toBe(44100);
      expect(session!.metadata.channels).toBe(2);
      expect(session!.statistics.totalSnapshots).toBe(0);
    });

    it('should accept custom metadata overrides', () => {
      service.startNewSession({ sampleRate: 96000, channels: 1 });

      const session = service.getCurrentSession();
      expect(session!.metadata.sampleRate).toBe(96000);
      expect(session!.metadata.channels).toBe(1);
    });

    it('should reset snapshots on new session', () => {
      service.addSnapshot({ loudness: { momentary_loudness: -14, short_term_loudness: -14, integrated_loudness: -14, loudness_range: 8, peak_dbfs: -1, true_peak_dbfs: -0.5 } });
      expect(service.getSnapshotCount()).toBe(1);

      service.startNewSession();
      expect(service.getSnapshotCount()).toBe(0);
    });
  });

  describe('addSnapshot', () => {
    it('should add snapshots to the session', () => {
      service.addSnapshot({ loudness: { momentary_loudness: -14, short_term_loudness: -14, integrated_loudness: -14, loudness_range: 8, peak_dbfs: -1, true_peak_dbfs: -0.5 } });
      service.addSnapshot({ loudness: { momentary_loudness: -12, short_term_loudness: -12, integrated_loudness: -13, loudness_range: 7, peak_dbfs: -0.5, true_peak_dbfs: -0.3 } });

      expect(service.getSnapshotCount()).toBe(2);
      const session = service.getCurrentSession();
      expect(session!.statistics.totalSnapshots).toBe(2);
    });

    it('should respect maxSnapshots limit by removing oldest', () => {
      // maxSnapshots is 10000 — we won't add that many but verify the shift logic
      // Access private field via any cast for testing
      (service as any).maxSnapshots = 3;

      service.addSnapshot({});
      service.addSnapshot({});
      service.addSnapshot({});
      service.addSnapshot({});

      expect(service.getSnapshotCount()).toBe(3);
    });

    it('should not add snapshot when no session exists', () => {
      service.destroy();
      service.addSnapshot({});

      expect(service.getSnapshotCount()).toBe(0);
    });

    it('should update running statistics from loudness data', () => {
      service.addSnapshot({
        loudness: { momentary_loudness: -14, short_term_loudness: -14, integrated_loudness: -14, loudness_range: 8, peak_dbfs: -1, true_peak_dbfs: -0.5 },
      });

      const session = service.getCurrentSession();
      expect(session!.statistics.peakLoudness).toBe(-14);
    });
  });

  describe('endCurrentSession', () => {
    it('should set endTime and calculate duration', () => {
      service.addSnapshot({});

      service.endCurrentSession();

      const session = service.getCurrentSession();
      expect(session!.endTime).toBeDefined();
      expect(session!.metadata.duration).toBeGreaterThanOrEqual(0);
    });

    it('should not throw when no session exists', () => {
      service.destroy();
      expect(() => service.endCurrentSession()).not.toThrow();
    });
  });

  describe('exportSession', () => {
    it('should export session as JSON and return a Blob', async () => {
      service.addSnapshot({
        loudness: { momentary_loudness: -14, short_term_loudness: -14, integrated_loudness: -14, loudness_range: 8, peak_dbfs: -1, true_peak_dbfs: -0.5 },
      });

      const blob = await service.exportSession({ format: 'json' });

      expect(blob).toBeInstanceOf(Blob);
      expect(blob.type).toBe('application/json');

      const text = await blob.text();
      const data = JSON.parse(text);
      expect(data.metadata).toBeDefined();
      expect(data.statistics).toBeDefined();
      expect(data.snapshots).toHaveLength(1);
    });

    it('should throw when no active session', async () => {
      service.destroy();

      await expect(service.exportSession()).rejects.toThrow('No active session to export');
    });
  });

  describe('exportCurrentSnapshot', () => {
    it('should export the last snapshot as JSON blob', async () => {
      service.addSnapshot({
        loudness: { momentary_loudness: -14, short_term_loudness: -14, integrated_loudness: -14, loudness_range: 8, peak_dbfs: -1, true_peak_dbfs: -0.5 },
      });

      const blob = await service.exportCurrentSnapshot('json');

      expect(blob).toBeInstanceOf(Blob);
      expect(blob.type).toBe('application/json');

      const text = await blob.text();
      const data = JSON.parse(text);
      expect(data.loudness).toBeDefined();
      expect(data.loudness.momentary_loudness).toBe(-14);
    });

    it('should export the last snapshot as CSV blob', async () => {
      service.addSnapshot({
        loudness: { momentary_loudness: -14, short_term_loudness: -14, integrated_loudness: -14, loudness_range: 8, peak_dbfs: -1, true_peak_dbfs: -0.5 },
      });

      const blob = await service.exportCurrentSnapshot('csv');

      expect(blob).toBeInstanceOf(Blob);
      expect(blob.type).toBe('text/csv');

      const text = await blob.text();
      expect(text).toContain('field,value');
      expect(text).toContain('momentary_loudness');
    });

    it('should throw when no snapshots available', async () => {
      // Constructor calls startNewSession which resets snapshots
      await expect(service.exportCurrentSnapshot()).rejects.toThrow('No snapshots available');
    });
  });

  describe('destroy', () => {
    it('should clear all state', () => {
      service.addSnapshot({});
      service.addSnapshot({});

      service.destroy();

      expect(service.getCurrentSession()).toBeNull();
      expect(service.getSnapshotCount()).toBe(0);
    });

    it('should be safe to call multiple times', () => {
      service.destroy();
      expect(() => service.destroy()).not.toThrow();
    });
  });
});
