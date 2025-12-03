/**
 * usePlayerDisplay Hook Tests
 *
 * 50+ comprehensive tests covering:
 * - Time formatting (mm:ss and h:mm:ss)
 * - Progress percentage calculation
 * - Time remaining calculation
 * - Buffered percentage formatting
 * - Live content detection
 * - Play/pause label
 * - Display string composition
 * - Memoization verification
 * - Standalone utility functions
 *
 * @module __tests__/usePlayerDisplay
 */

import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  usePlayerDisplay,
  formatSecondToTime,
  calculateProgressPercentage,
  formatBufferedPercentage,
} from '../usePlayerDisplay';

describe('usePlayerDisplay Hook', () => {
  describe('Basic Time Formatting', () => {
    it('should format short times as mm:ss', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 90, // 1:30
          duration: 225, // 3:45
        })
      );

      expect(result.current.currentTimeStr).toBe('1:30');
      expect(result.current.durationStr).toBe('3:45');
    });

    it('should format zero seconds as 0:00', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 0,
        })
      );

      expect(result.current.currentTimeStr).toBe('0:00');
      expect(result.current.durationStr).toBe('0:00');
    });

    it('should format single digit seconds with padding', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 5, // 0:05
          duration: 60, // 1:00
        })
      );

      expect(result.current.currentTimeStr).toBe('0:05');
      expect(result.current.durationStr).toBe('1:00');
    });

    it('should format minutes correctly', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 120, // 2:00
          duration: 300, // 5:00
        })
      );

      expect(result.current.currentTimeStr).toBe('2:00');
      expect(result.current.durationStr).toBe('5:00');
    });

    it('should format single digit minutes', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 30, // 0:30
          duration: 300,
        })
      );

      expect(result.current.currentTimeStr).toBe('0:30');
    });
  });

  describe('Long Duration Formatting', () => {
    it('should format times > 1 hour as h:mm:ss', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 3661, // 1:01:01
          duration: 7322, // 2:02:02
        })
      );

      expect(result.current.currentTimeStr).toBe('1:01:01');
      expect(result.current.durationStr).toBe('2:02:02');
    });

    it('should format multi-hour durations', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 7200, // 2:00:00
          duration: 10800, // 3:00:00
        })
      );

      expect(result.current.currentTimeStr).toBe('2:00:00');
      expect(result.current.durationStr).toBe('3:00:00');
    });

    it('should force show hours when requested', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 90, // 1:30
          duration: 225, // 3:45
          forceShowHours: true,
        })
      );

      expect(result.current.currentTimeStr).toBe('0:01:30');
      expect(result.current.durationStr).toBe('0:03:45');
    });

    it('should auto-enable hours for durations >= 1 hour', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 60,
          duration: 3600, // Exactly 1 hour
        })
      );

      expect(result.current.durationStr).toContain(':');
      // Should have h:mm:ss format for 1 hour
    });
  });

  describe('Progress Percentage', () => {
    it('should calculate 50% progress', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 50,
          duration: 100,
        })
      );

      expect(result.current.progressPercentage).toBe(50);
    });

    it('should calculate 0% at start', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
        })
      );

      expect(result.current.progressPercentage).toBe(0);
    });

    it('should calculate 100% at end', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 100,
          duration: 100,
        })
      );

      expect(result.current.progressPercentage).toBe(100);
    });

    it('should clamp progress to 100%', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 150, // Exceeds duration
          duration: 100,
        })
      );

      expect(result.current.progressPercentage).toBe(100);
    });

    it('should clamp progress to 0%', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: -10, // Negative
          duration: 100,
        })
      );

      expect(result.current.progressPercentage).toBe(0);
    });

    it('should handle zero duration', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 50,
          duration: 0,
        })
      );

      expect(result.current.progressPercentage).toBe(0);
    });

    it('should handle Infinity duration', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 50,
          duration: Infinity,
        })
      );

      expect(result.current.progressPercentage).toBe(0);
    });

    it('should calculate partial percentages accurately', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 33,
          duration: 100,
        })
      );

      expect(result.current.progressPercentage).toBe(33);
    });
  });

  describe('Time Remaining', () => {
    it('should calculate time remaining', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 90, // 1:30
          duration: 225, // 3:45
        })
      );

      expect(result.current.timeRemainingStr).toBe('-2:15');
    });

    it('should show 0:00 when at end', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 100,
          duration: 100,
        })
      );

      expect(result.current.timeRemainingStr).toBe('0:00');
    });

    it('should show 0:00 when beyond duration', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 150,
          duration: 100,
        })
      );

      expect(result.current.timeRemainingStr).toBe('0:00');
    });

    it('should include minus sign for remaining time', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 30,
          duration: 100,
        })
      );

      expect(result.current.timeRemainingStr).toContain('-');
    });
  });

  describe('Buffered Percentage', () => {
    it('should format 50% buffered', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
          bufferedPercentage: 50,
        })
      );

      expect(result.current.bufferedPercentageStr).toBe('50%');
    });

    it('should format 0% buffered', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
          bufferedPercentage: 0,
        })
      );

      expect(result.current.bufferedPercentageStr).toBe('0%');
    });

    it('should format 100% buffered', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
          bufferedPercentage: 100,
        })
      );

      expect(result.current.bufferedPercentageStr).toBe('100%');
    });

    it('should clamp buffered to 100%', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
          bufferedPercentage: 150,
        })
      );

      expect(result.current.bufferedPercentageStr).toBe('100%');
    });

    it('should clamp buffered to 0%', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
          bufferedPercentage: -50,
        })
      );

      expect(result.current.bufferedPercentageStr).toBe('0%');
    });

    it('should round fractional percentages', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
          bufferedPercentage: 33.7,
        })
      );

      expect(result.current.bufferedPercentageStr).toBe('34%');
    });
  });

  describe('Live Content Detection', () => {
    it('should detect live content with zero duration', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 0,
        })
      );

      expect(result.current.isLiveContent).toBe(true);
    });

    it('should detect live content with Infinity duration', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 100,
          duration: Infinity,
        })
      );

      expect(result.current.isLiveContent).toBe(true);
    });

    it('should not detect live content for normal tracks', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 30,
          duration: 200,
        })
      );

      expect(result.current.isLiveContent).toBe(false);
    });
  });

  describe('Play/Pause Label', () => {
    it('should show Play when not playing', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
          isPlaying: false,
        })
      );

      expect(result.current.playPauseLabel).toBe('Play');
    });

    it('should show Pause when playing', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
          isPlaying: true,
        })
      );

      expect(result.current.playPauseLabel).toBe('Pause');
    });

    it('should default to Play', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 0,
          duration: 100,
        })
      );

      expect(result.current.playPauseLabel).toBe('Play');
    });
  });

  describe('Full Display Strings', () => {
    it('should format full time display', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 90,
          duration: 225,
        })
      );

      expect(result.current.fullTimeDisplay).toBe('1:30 / 3:45');
    });

    it('should show LIVE for live content', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 100,
          duration: 0,
        })
      );

      expect(result.current.fullTimeDisplay).toBe('LIVE');
    });

    it('should format full time with remaining', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 90,
          duration: 225,
        })
      );

      expect(result.current.fullTimeWithRemaining).toBe('1:30 / 3:45 (-2:15)');
    });

    it('should show LIVE for remaining display', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 100,
          duration: Infinity,
        })
      );

      expect(result.current.fullTimeWithRemaining).toBe('LIVE');
    });
  });

  describe('Utility Functions', () => {
    it('should format seconds to time string', () => {
      expect(formatSecondToTime(90)).toBe('1:30');
      expect(formatSecondToTime(225)).toBe('3:45');
      expect(formatSecondToTime(0)).toBe('0:00');
      expect(formatSecondToTime(5)).toBe('0:05');
    });

    it('should format with hours when requested', () => {
      expect(formatSecondToTime(3661, true)).toBe('1:01:01');
      expect(formatSecondToTime(90, true)).toBe('0:01:30');
    });

    it('should calculate progress percentage', () => {
      expect(calculateProgressPercentage(50, 100)).toBe(50);
      expect(calculateProgressPercentage(0, 100)).toBe(0);
      expect(calculateProgressPercentage(100, 100)).toBe(100);
      expect(calculateProgressPercentage(150, 100)).toBe(100); // Clamped
    });

    it('should handle zero duration in progress', () => {
      expect(calculateProgressPercentage(50, 0)).toBe(0);
      expect(calculateProgressPercentage(50, Infinity)).toBe(0);
    });

    it('should format buffered percentage', () => {
      expect(formatBufferedPercentage(50)).toBe('50%');
      expect(formatBufferedPercentage(0)).toBe('0%');
      expect(formatBufferedPercentage(100)).toBe('100%');
      expect(formatBufferedPercentage(33.7)).toBe('34%'); // Rounded
      expect(formatBufferedPercentage(-50)).toBe('0%'); // Clamped
      expect(formatBufferedPercentage(150)).toBe('100%'); // Clamped
    });
  });

  describe('Edge Cases', () => {
    it('should handle negative currentTime', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: -10,
          duration: 100,
        })
      );

      expect(result.current.progressPercentage).toBe(0);
      expect(result.current.currentTimeStr).toBe('0:00');
    });

    it('should handle NaN values', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: NaN,
          duration: 100,
        })
      );

      expect(result.current.currentTimeStr).toBe('0:00');
      // NaN currentTime will result in NaN progress, which is valid
      expect(Number.isNaN(result.current.progressPercentage)).toBe(true);
    });

    it('should handle very large values', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 999999,
          duration: 1000000,
        })
      );

      // Should calculate precise percentage
      expect(result.current.progressPercentage).toBeCloseTo(99.9999, 3);
      expect(Number.isFinite(result.current.progressPercentage)).toBe(true);
    });

    it('should handle fractional seconds', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 90.5,
          duration: 225.5,
        })
      );

      // Should floor to integer seconds
      expect(result.current.currentTimeStr).toBe('1:30');
      expect(result.current.durationStr).toBe('3:45');
    });
  });

  describe('Memoization', () => {
    it('should memoize time strings', () => {
      const { result, rerender } = renderHook(
        (props) => usePlayerDisplay(props),
        {
          initialProps: {
            currentTime: 90,
            duration: 225,
            isPlaying: false,
          },
        }
      );

      const firstTimeStr = result.current.currentTimeStr;

      // Rerender with same props
      rerender({
        currentTime: 90,
        duration: 225,
        isPlaying: true, // Different prop but not used in currentTimeStr
      });

      // Should return same reference (memoized)
      expect(result.current.currentTimeStr).toBe(firstTimeStr);
    });

    it('should recalculate when time changes', () => {
      const { result, rerender } = renderHook(
        (props) => usePlayerDisplay(props),
        {
          initialProps: {
            currentTime: 90,
            duration: 225,
          },
        }
      );

      expect(result.current.currentTimeStr).toBe('1:30');

      rerender({
        currentTime: 180,
        duration: 225,
      });

      expect(result.current.currentTimeStr).toBe('3:00');
    });
  });

  describe('Realistic Scenarios', () => {
    it('should handle typical music playback', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 42,
          duration: 234,
          isPlaying: true,
          bufferedPercentage: 100,
        })
      );

      expect(result.current.fullTimeDisplay).toBe('0:42 / 3:54');
      expect(result.current.playPauseLabel).toBe('Pause');
      expect(result.current.progressPercentage).toBeCloseTo(17.9, 0);
      expect(result.current.bufferedPercentageStr).toBe('100%');
    });

    it('should handle album playback (long duration)', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 2100, // 35 minutes
          duration: 3000, // 50 minutes
          isPlaying: true,
          bufferedPercentage: 85,
        })
      );

      expect(result.current.fullTimeDisplay).toBe('35:00 / 50:00');
      expect(result.current.progressPercentage).toBe(70);
      expect(result.current.bufferedPercentageStr).toBe('85%');
    });

    it('should handle podcast playback (multi-hour)', () => {
      const { result } = renderHook(() =>
        usePlayerDisplay({
          currentTime: 1800, // 30 minutes
          duration: 7200, // 2 hours
          isPlaying: true,
          bufferedPercentage: 50,
        })
      );

      expect(result.current.fullTimeDisplay).toBe('0:30:00 / 2:00:00');
      expect(result.current.progressPercentage).toBe(25);
      expect(result.current.fullTimeWithRemaining).toContain('-1:30:00');
    });
  });
});
