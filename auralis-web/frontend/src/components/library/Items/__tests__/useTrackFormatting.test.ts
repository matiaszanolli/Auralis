/**
 * useTrackFormatting Hook Tests
 *
 * Tests for formatting utilities:
 * - Duration formatting (mm:ss)
 */

import { vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useTrackFormatting } from '../tracks/useTrackFormatting';

describe('useTrackFormatting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Hook Initialization', () => {
    it('should expose formatDuration utility', () => {
      const { result } = renderHook(() => useTrackFormatting());

      expect(result.current.formatDuration).toBeDefined();
      expect(typeof result.current.formatDuration).toBe('function');
    });
  });

  describe('formatDuration', () => {
    it('should format 0 seconds as "0:00"', () => {
      const { result } = renderHook(() => useTrackFormatting());

      const formatted = result.current.formatDuration(0);

      expect(formatted).toBe('0:00');
    });

    it('should format 60 seconds as "1:00"', () => {
      const { result } = renderHook(() => useTrackFormatting());

      const formatted = result.current.formatDuration(60);

      expect(formatted).toBe('1:00');
    });

    it('should format 3661 seconds as "61:01"', () => {
      const { result } = renderHook(() => useTrackFormatting());

      const formatted = result.current.formatDuration(3661);

      expect(formatted).toBe('61:01');
    });

    it('should pad single-digit seconds', () => {
      const { result } = renderHook(() => useTrackFormatting());

      const formatted = result.current.formatDuration(65);

      expect(formatted).toBe('1:05');
    });

    it('should handle large durations (hours)', () => {
      const { result } = renderHook(() => useTrackFormatting());

      // 1 hour = 3600 seconds
      const formatted = result.current.formatDuration(3600);

      expect(formatted).toBe('60:00');
    });

    it('should handle 2 hours duration', () => {
      const { result } = renderHook(() => useTrackFormatting());

      // 2 hours 30 minutes 45 seconds
      const formatted = result.current.formatDuration(9045);

      expect(formatted).toBe('150:45');
    });

    it('should pad minutes with single digit', () => {
      const { result } = renderHook(() => useTrackFormatting());

      // 5 minutes 30 seconds
      const formatted = result.current.formatDuration(330);

      expect(formatted).toBe('5:30');
    });

    it('should pad seconds with leading zero', () => {
      const { result } = renderHook(() => useTrackFormatting());

      // 2 minutes 5 seconds
      const formatted = result.current.formatDuration(125);

      expect(formatted).toBe('2:05');
    });

    it('should handle edge case: 59 seconds', () => {
      const { result } = renderHook(() => useTrackFormatting());

      const formatted = result.current.formatDuration(59);

      expect(formatted).toBe('0:59');
    });

    it('should handle negative durations gracefully', () => {
      const { result } = renderHook(() => useTrackFormatting());

      // Negative values should not crash, behavior depends on implementation
      // Most likely will show "0:00" or similar
      const formatted = result.current.formatDuration(-10);

      // Should not throw and should return a string
      expect(typeof formatted).toBe('string');
    });

    it('should handle decimal seconds (truncate)', () => {
      const { result } = renderHook(() => useTrackFormatting());

      // 125.7 seconds -> should truncate to 125 -> 2:05
      const formatted = result.current.formatDuration(125.7);

      expect(formatted).toBe('2:05');
    });
  });

  describe('Handler Stability', () => {
    it('should maintain referential equality across renders', () => {
      const { result, rerender } = renderHook(() => useTrackFormatting());

      const initialHandler = result.current.formatDuration;

      rerender();

      expect(result.current.formatDuration).toBe(initialHandler);
    });

    it('should produce consistent results across calls', () => {
      const { result } = renderHook(() => useTrackFormatting());

      const seconds = 185; // 3 minutes 5 seconds

      const result1 = result.current.formatDuration(seconds);
      const result2 = result.current.formatDuration(seconds);

      expect(result1).toBe(result2);
      expect(result1).toBe('3:05');
    });
  });

  describe('Common Track Durations', () => {
    it('should format typical 3-minute song', () => {
      const { result } = renderHook(() => useTrackFormatting());

      // 3 minutes
      const formatted = result.current.formatDuration(180);

      expect(formatted).toBe('3:00');
    });

    it('should format typical 4-minute song', () => {
      const { result } = renderHook(() => useTrackFormatting());

      // 4 minutes 32 seconds
      const formatted = result.current.formatDuration(272);

      expect(formatted).toBe('4:32');
    });

    it('should format long 10-minute track', () => {
      const { result } = renderHook(() => useTrackFormatting());

      // 10 minutes 45 seconds
      const formatted = result.current.formatDuration(645);

      expect(formatted).toBe('10:45');
    });
  });
});
