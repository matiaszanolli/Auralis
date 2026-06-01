/**
 * Tests for useStreamingProgressMetrics (#3939 / CQ-3)
 *
 * Validates the buffer-health / progress domain math extracted out of
 * StreamingProgressBar so the computations are covered independently of render.
 */

import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { tokens } from '@/design-system';
import {
  useStreamingProgressMetrics,
  type StreamingProgressMetricsInput,
} from '../useStreamingProgressMetrics';

const baseInput: StreamingProgressMetricsInput = {
  progress: 0,
  bufferedSamples: 0,
  totalChunks: 0,
  processedChunks: 0,
  sampleRate: 48000,
};

const run = (overrides: Partial<StreamingProgressMetricsInput> = {}) =>
  renderHook(() => useStreamingProgressMetrics({ ...baseInput, ...overrides })).result
    .current;

describe('useStreamingProgressMetrics', () => {
  describe('bufferedDuration', () => {
    it('converts samples to seconds using the sample rate', () => {
      expect(run({ bufferedSamples: 96000, sampleRate: 48000 }).bufferedDuration).toBe(2);
    });

    it('returns 0 for a zero sample rate instead of NaN/Infinity', () => {
      const m = run({ bufferedSamples: 96000, sampleRate: 0 });
      expect(m.bufferedDuration).toBe(0);
      expect(Number.isFinite(m.bufferedDuration)).toBe(true);
    });
  });

  describe('estimatedRemaining', () => {
    it('is 0 when total chunks are unknown', () => {
      expect(run({ totalChunks: 0, processedChunks: 0 }).estimatedRemaining).toBe(0);
    });

    it('estimates 0.2s per remaining chunk', () => {
      expect(
        run({ totalChunks: 10, processedChunks: 4 }).estimatedRemaining,
      ).toBeCloseTo(1.2);
    });

    it('never goes negative when processed exceeds total', () => {
      expect(run({ totalChunks: 5, processedChunks: 8 }).estimatedRemaining).toBe(0);
    });
  });

  describe('bufferPercentage', () => {
    it('is 0 when nothing is buffered', () => {
      expect(run({ bufferedSamples: 0 }).bufferPercentage).toBe(0);
    });

    it('is relative to the 2s healthy target', () => {
      // 1s buffered → 50% of the 2s target.
      expect(run({ bufferedSamples: 48000, sampleRate: 48000 }).bufferPercentage).toBe(50);
    });

    it('caps at 100 even when over-buffered', () => {
      expect(
        run({ bufferedSamples: 480000, sampleRate: 48000 }).bufferPercentage,
      ).toBe(100);
    });
  });

  describe('bufferStatus', () => {
    const cases: Array<[number, string, string]> = [
      [0.25, 'Critical', tokens.colors.semantic.error],
      [0.75, 'Low', tokens.colors.semantic.warning],
      [1.5, 'Adequate', tokens.colors.semantic.info],
      [3.0, 'Healthy', tokens.colors.semantic.success],
    ];

    it.each(cases)(
      'at %ss buffered → %s',
      (seconds, label, color) => {
        const status = run({
          bufferedSamples: seconds * 48000,
          sampleRate: 48000,
        }).bufferStatus;
        expect(status.label).toBe(label);
        expect(status.color).toBe(color);
      },
    );
  });

  describe('progressBarColor', () => {
    it.each([
      [100, tokens.colors.semantic.success],
      [80, tokens.colors.semantic.info],
      [60, tokens.colors.semantic.warning],
      [10, tokens.colors.semantic.error],
    ])('progress %i → expected color', (progress, color) => {
      expect(run({ progress }).progressBarColor).toBe(color);
    });
  });

  describe('bufferFillWidth', () => {
    it('mirrors bufferPercentage, capped at 100', () => {
      const m = run({ bufferedSamples: 480000, sampleRate: 48000 });
      expect(m.bufferFillWidth).toBe(100);
      expect(m.bufferFillWidth).toBe(Math.min(100, m.bufferPercentage));
    });
  });
});
