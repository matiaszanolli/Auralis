/**
 * useVisualizationOptimization Hook Tests
 *
 * Tests for the visualization performance optimization hook.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

// ---- shared mock state used by the vi.mock factory ----
// vi.hoisted() ensures these exist at hoist time so the factory can
// reference them safely. See https://vitest.dev/api/vi.html#vi-hoisted
const mocks = vi.hoisted(() => ({
  getMetrics: vi.fn().mockReturnValue({
    fps: 60, frameTime: 16.6, renderTime: 8, cpuUsage: 30,
    memoryUsage: 50, droppedFrames: 0, adaptiveQuality: 1.0,
    dataPoints: 1024, bufferHealth: 1.0,
  }),
  getQualityLevel: vi.fn().mockReturnValue(1.0),
  shouldRender: vi.fn().mockReturnValue(true),
  optimizeData: vi.fn((data: number[]) => data),
  startRender: vi.fn(),
  endRender: vi.fn(),
  cleanup: vi.fn(),
  updateBufferHealth: vi.fn(),
  monitorStart: vi.fn(),
  monitorEnd: vi.fn(),
  getPerformanceMonitor: vi.fn(),
  Ctor: vi.fn(),
}));

// Wire up getPerformanceMonitor return value
mocks.getPerformanceMonitor.mockReturnValue({
  start: mocks.monitorStart,
  end: mocks.monitorEnd,
  getAverage: vi.fn().mockReturnValue(0),
  getStats: vi.fn().mockReturnValue({}),
  clear: vi.fn(),
});

// Wire up the constructor
mocks.Ctor.mockImplementation(() => ({
  getMetrics: mocks.getMetrics,
  getQualityLevel: mocks.getQualityLevel,
  shouldRender: mocks.shouldRender,
  optimizeData: mocks.optimizeData,
  startRender: mocks.startRender,
  endRender: mocks.endRender,
  cleanup: mocks.cleanup,
  updateBufferHealth: mocks.updateBufferHealth,
  getPerformanceMonitor: mocks.getPerformanceMonitor,
}));

vi.mock('@/utils/performanceOptimizer', () => ({
  PerformanceOptimizer: mocks.Ctor,
  PerformanceMonitor: vi.fn(),
}));

// Import after mock setup
import { useVisualizationOptimization } from '../useVisualizationOptimization';

describe('useVisualizationOptimization', () => {
  beforeEach(() => {
    // Clear call history only — keep implementations
    Object.values(mocks).forEach((m) => m.mockClear());

    // Re-apply default return values that mockClear strips
    mocks.shouldRender.mockReturnValue(true);
    mocks.optimizeData.mockImplementation((d: number[]) => d);
    mocks.getQualityLevel.mockReturnValue(1.0);
    mocks.getMetrics.mockReturnValue({
      fps: 60, frameTime: 16.6, renderTime: 8, cpuUsage: 30,
      memoryUsage: 50, droppedFrames: 0, adaptiveQuality: 1.0,
      dataPoints: 1024, bufferHealth: 1.0,
    });
    mocks.getPerformanceMonitor.mockReturnValue({
      start: mocks.monitorStart,
      end: mocks.monitorEnd,
      getAverage: vi.fn().mockReturnValue(0),
      getStats: vi.fn().mockReturnValue({}),
      clear: vi.fn(),
    });
    mocks.Ctor.mockImplementation(() => ({
      getMetrics: mocks.getMetrics,
      getQualityLevel: mocks.getQualityLevel,
      shouldRender: mocks.shouldRender,
      optimizeData: mocks.optimizeData,
      startRender: mocks.startRender,
      endRender: mocks.endRender,
      cleanup: mocks.cleanup,
      updateBufferHealth: mocks.updateBufferHealth,
      getPerformanceMonitor: mocks.getPerformanceMonitor,
    }));
  });

  describe('initialization', () => {
    it('returns expected shape with default options', () => {
      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      expect(result.current.stats).toBeDefined();
      expect(result.current.qualityLevel).toBe(1.0);
      expect(typeof result.current.shouldRender).toBe('function');
      expect(typeof result.current.optimizeData).toBe('function');
      expect(typeof result.current.startRender).toBe('function');
      expect(typeof result.current.endRender).toBe('function');
      expect(typeof result.current.updateConfig).toBe('function');
    });

    it('initializes with default performance metrics', () => {
      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      expect(result.current.stats.fps).toBe(0);
      expect(result.current.stats.adaptiveQuality).toBe(1.0);
      expect(result.current.stats.bufferHealth).toBe(1.0);
    });

    it('creates a PerformanceOptimizer with provided config', () => {
      renderHook(() =>
        useVisualizationOptimization({
          enableMonitoring: false,
          targetFPS: 30,
          maxDataPoints: 512,
        })
      );

      expect(mocks.Ctor).toHaveBeenCalledWith(
        expect.objectContaining({
          targetFPS: 30,
          maxDataPoints: 512,
          adaptiveQuality: true,
        })
      );
    });

    it('creates a PerformanceMonitor when monitoring is enabled', () => {
      renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: true })
      );

      expect(mocks.getPerformanceMonitor).toHaveBeenCalled();
    });

    it('does not create a PerformanceMonitor when monitoring is disabled', () => {
      renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      expect(mocks.getPerformanceMonitor).not.toHaveBeenCalled();
    });
  });

  describe('shouldRender', () => {
    it('delegates to optimizer and returns true', () => {
      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      expect(result.current.shouldRender()).toBe(true);
      expect(mocks.shouldRender).toHaveBeenCalled();
    });

    it('returns false when optimizer says no', () => {
      mocks.shouldRender.mockReturnValueOnce(false);

      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      expect(result.current.shouldRender()).toBe(false);
    });
  });

  describe('optimizeData', () => {
    it('delegates to optimizer and returns result', () => {
      mocks.optimizeData.mockReturnValueOnce([1, 3, 5]);

      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      const optimized = result.current.optimizeData([1, 2, 3, 4, 5]);

      expect(mocks.optimizeData).toHaveBeenCalledWith([1, 2, 3, 4, 5]);
      expect(optimized).toEqual([1, 3, 5]);
    });

    it('instruments with monitor when monitoring is enabled', () => {
      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: true })
      );

      result.current.optimizeData([1, 2]);

      expect(mocks.monitorStart).toHaveBeenCalledWith('dataOptimization');
      expect(mocks.monitorEnd).toHaveBeenCalledWith('dataOptimization');
    });
  });

  describe('startRender / endRender', () => {
    it('calls optimizer startRender and endRender', () => {
      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      result.current.startRender();
      expect(mocks.startRender).toHaveBeenCalled();

      result.current.endRender();
      expect(mocks.endRender).toHaveBeenCalled();
    });

    it('records monitoring start/end when monitoring enabled', () => {
      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: true })
      );

      result.current.startRender();
      expect(mocks.monitorStart).toHaveBeenCalledWith('render');

      result.current.endRender();
      expect(mocks.monitorEnd).toHaveBeenCalledWith('render');
    });

    it('does not call monitor when monitoring is disabled', () => {
      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      result.current.startRender();
      result.current.endRender();

      expect(mocks.monitorStart).not.toHaveBeenCalled();
      expect(mocks.monitorEnd).not.toHaveBeenCalled();
    });
  });

  describe('updateConfig', () => {
    it('calls updateBufferHealth when adaptiveQuality is enabled', () => {
      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      result.current.updateConfig({ adaptiveQuality: true });

      expect(mocks.updateBufferHealth).toHaveBeenCalledWith(90, 100);
    });

    it('does nothing for non-adaptive config changes', () => {
      const { result } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      result.current.updateConfig({ targetFPS: 30 });

      expect(mocks.updateBufferHealth).not.toHaveBeenCalled();
    });
  });

  describe('cleanup', () => {
    it('calls optimizer cleanup on unmount', () => {
      const { unmount } = renderHook(() =>
        useVisualizationOptimization({ enableMonitoring: false })
      );

      unmount();

      expect(mocks.cleanup).toHaveBeenCalled();
    });
  });

  describe('config changes', () => {
    it('reinitializes optimizer when config changes', () => {
      const { rerender } = renderHook(
        ({ targetFPS }) =>
          useVisualizationOptimization({ targetFPS, enableMonitoring: false }),
        { initialProps: { targetFPS: 30 } }
      );

      const callsAfterMount = mocks.Ctor.mock.calls.length;

      rerender({ targetFPS: 60 });

      expect(mocks.Ctor.mock.calls.length).toBeGreaterThan(callsAfterMount);
      // The latest call should have the new targetFPS
      const lastCall = mocks.Ctor.mock.calls.at(-1)?.[0];
      expect(lastCall).toEqual(expect.objectContaining({ targetFPS: 60 }));
    });
  });
});
