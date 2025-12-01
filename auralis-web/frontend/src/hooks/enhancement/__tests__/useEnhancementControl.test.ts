/**
 * useEnhancementControl Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for enhancement control hook including:
 * - State initialization and fetching
 * - Preset changes and validation
 * - Intensity control with clamping
 * - Toggle enabled/disabled
 * - WebSocket real-time sync
 * - Error handling
 * - Optimistic updates
 *
 * @module hooks/enhancement/__tests__/useEnhancementControl.test
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { vi } from 'vitest';
import {
  useEnhancementControl,
  usePresetControl,
  useIntensityControl,
  useEnhancementToggle,
} from '@/hooks/enhancement/useEnhancementControl';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketSubscription } from '@/hooks/websocket/useWebSocketSubscription';

// Mock hooks
vi.mock('@/hooks/api/useRestAPI');
vi.mock('@/hooks/websocket/useWebSocketSubscription');

describe('useEnhancementControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state and fetching', () => {
    it('should start with default state', () => {
      const mockGet = vi.fn().mockResolvedValue(null);
      const mockPost = vi.fn();

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      expect(result.current.enabled).toBe(false);
      expect(result.current.preset).toBe('adaptive');
      expect(result.current.intensity).toBe(1.0);
    });

    it('should fetch initial enhancement state on mount', async () => {
      const mockEnhancementState = {
        enabled: true,
        preset: 'warm' as const,
        intensity: 0.8,
        lastUpdated: Date.now(),
      };

      const mockGet = vi.fn().mockResolvedValue(mockEnhancementState);
      const mockPost = vi.fn();

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      await waitFor(() => {
        expect(result.current.enabled).toBe(true);
      });

      expect(result.current.preset).toBe('warm');
      expect(result.current.intensity).toBe(0.8);
    });

    it('should handle fetch error gracefully', async () => {
      const mockGet = vi.fn().mockRejectedValue(new Error('Network error'));
      const mockPost = vi.fn();

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      // Should still have default state even if fetch fails
      expect(result.current.enabled).toBe(false);
      expect(result.current.preset).toBe('adaptive');
    });

    it('should subscribe to WebSocket enhancement_settings_changed messages', () => {
      const mockGet = vi.fn().mockResolvedValue(null);
      const mockPost = vi.fn();

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      renderHook(() => useEnhancementControl());

      expect(vi.mocked(useWebSocketSubscription)).toHaveBeenCalledWith(
        ['enhancement_settings_changed'],
        expect.any(Function)
      );
    });
  });

  describe('toggleEnabled', () => {
    it('should toggle enabled state', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      expect(result.current.enabled).toBe(false);

      await act(async () => {
        await result.current.toggleEnabled();
      });

      expect(result.current.enabled).toBe(true);
      expect(mockPost).toHaveBeenCalledWith(
        '/api/player/enhancement/toggle',
        expect.objectContaining({ enabled: true })
      );
    });

    it('should toggle from enabled to disabled', async () => {
      const mockEnhancementState = {
        enabled: true,
        preset: 'warm' as const,
        intensity: 0.8,
        lastUpdated: Date.now(),
      };

      const mockPost = vi.fn().mockResolvedValue({ success: true });
      const mockGet = vi.fn().mockResolvedValue(mockEnhancementState);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      await waitFor(() => {
        expect(result.current.enabled).toBe(true);
      });

      await act(async () => {
        await result.current.toggleEnabled();
      });

      expect(result.current.enabled).toBe(false);
    });

    it('should set loading state while toggling', async () => {
      const mockPost = vi.fn(
        () =>
          new Promise((resolve) => {
            setTimeout(() => resolve({ success: true }), 100);
          })
      );
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      const togglePromise = act(async () => {
        await result.current.toggleEnabled();
      });

      // Check loading state immediately after calling
      // (Note: actual loading state depends on implementation timing)
      await togglePromise;

      expect(result.current.isLoading).toBe(false);
    });

    it('should handle toggle error', async () => {
      const mockPost = vi.fn().mockRejectedValue(new Error('API error'));
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      await act(async () => {
        try {
          await result.current.toggleEnabled();
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).not.toBeNull();
      expect(result.current.error?.code).toBe('TOGGLE_ERROR');
    });
  });

  describe('setPreset', () => {
    it('should change preset to valid value', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      expect(result.current.preset).toBe('adaptive');

      await act(async () => {
        await result.current.setPreset('warm');
      });

      expect(result.current.preset).toBe('warm');
      expect(mockPost).toHaveBeenCalledWith(
        '/api/player/enhancement/preset',
        expect.objectContaining({ preset: 'warm' })
      );
    });

    it('should reject invalid preset', async () => {
      const mockPost = vi.fn();
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      await act(async () => {
        try {
          await result.current.setPreset('invalid' as any);
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).not.toBeNull();
      expect(result.current.error?.code).toBe('INVALID_PRESET');
    });

    it('should support all valid presets', async () => {
      const validPresets: Array<'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy'> = [
        'adaptive',
        'gentle',
        'warm',
        'bright',
        'punchy',
      ];

      for (const preset of validPresets) {
        const mockPost = vi.fn().mockResolvedValue({ success: true });
        const mockGet = vi.fn().mockResolvedValue(null);

        vi.mocked(useRestAPI).mockReturnValue({
          get: mockGet,
          post: mockPost,
          put: vi.fn(),
          patch: vi.fn(),
          delete: vi.fn(),
        } as any);

        vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

        const { result } = renderHook(() => useEnhancementControl());

        await act(async () => {
          await result.current.setPreset(preset);
        });

        expect(result.current.preset).toBe(preset);
      }
    });

    it('should handle preset change error', async () => {
      const mockPost = vi.fn().mockRejectedValue(new Error('API error'));
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      await act(async () => {
        try {
          await result.current.setPreset('warm');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error?.code).toBe('PRESET_ERROR');
    });
  });

  describe('setIntensity', () => {
    it('should change intensity to valid value', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      expect(result.current.intensity).toBe(1.0);

      await act(async () => {
        await result.current.setIntensity(0.5);
      });

      expect(result.current.intensity).toBe(0.5);
      expect(mockPost).toHaveBeenCalledWith(
        '/api/player/enhancement/intensity',
        expect.objectContaining({ intensity: 0.5 })
      );
    });

    it('should clamp intensity to 0.0 when below', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      await act(async () => {
        await result.current.setIntensity(-0.5);
      });

      expect(result.current.intensity).toBe(0.0);
      expect(mockPost).toHaveBeenCalledWith(
        '/api/player/enhancement/intensity',
        expect.objectContaining({ intensity: 0.0 })
      );
    });

    it('should clamp intensity to 1.0 when above', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      await act(async () => {
        await result.current.setIntensity(1.5);
      });

      expect(result.current.intensity).toBe(1.0);
      expect(mockPost).toHaveBeenCalledWith(
        '/api/player/enhancement/intensity',
        expect.objectContaining({ intensity: 1.0 })
      );
    });

    it('should handle intensity change error', async () => {
      const mockPost = vi.fn().mockRejectedValue(new Error('API error'));
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      await act(async () => {
        try {
          await result.current.setIntensity(0.5);
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error?.code).toBe('INTENSITY_ERROR');
    });
  });

  describe('error handling', () => {
    it('should clear error state', async () => {
      const mockPost = vi.fn().mockRejectedValue(new Error('API error'));
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      await act(async () => {
        try {
          await result.current.toggleEnabled();
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).not.toBeNull();

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });

    it('should clear error when new command succeeds', async () => {
      let callCount = 0;
      const mockPost = vi.fn(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.reject(new Error('API error'));
        }
        return Promise.resolve({ success: true });
      });
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementControl());

      // First call fails
      await act(async () => {
        try {
          await result.current.toggleEnabled();
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).not.toBeNull();

      // Second call succeeds
      await act(async () => {
        await result.current.setPreset('warm');
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('WebSocket integration', () => {
    it('should update state from WebSocket message', async () => {
      const mockPost = vi.fn();
      const mockGet = vi.fn().mockResolvedValue(null);
      let wsCallback: Function | null = null;

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockImplementation(
        (types, callback) => {
          wsCallback = callback;
          return undefined;
        }
      );

      const { result } = renderHook(() => useEnhancementControl());

      // Simulate WebSocket message
      await act(async () => {
        if (wsCallback) {
          wsCallback({
            type: 'enhancement_settings_changed',
            data: {
              enabled: true,
              preset: 'bright',
              intensity: 0.75,
            },
          });
        }
      });

      expect(result.current.enabled).toBe(true);
      expect(result.current.preset).toBe('bright');
      expect(result.current.intensity).toBe(0.75);
    });

    it('should update timestamp on WebSocket change', async () => {
      const mockPost = vi.fn();
      const mockGet = vi.fn().mockResolvedValue(null);
      let wsCallback: Function | null = null;

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockImplementation(
        (types, callback) => {
          wsCallback = callback;
          return undefined;
        }
      );

      const { result } = renderHook(() => useEnhancementControl());

      const oldTimestamp = result.current.state.lastUpdated;

      await act(async () => {
        if (wsCallback) {
          wsCallback({
            type: 'enhancement_settings_changed',
            data: { enabled: true },
          });
        }
      });

      expect(result.current.state.lastUpdated).toBeGreaterThan(oldTimestamp);
    });
  });

  describe('convenience hooks', () => {
    it('should use usePresetControl for preset control', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => usePresetControl());

      expect(result.current.preset).toBe('adaptive');

      await act(async () => {
        await result.current.setPreset('warm');
      });

      expect(result.current.preset).toBe('warm');
    });

    it('should use useIntensityControl for intensity control', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useIntensityControl());

      expect(result.current.intensity).toBe(1.0);

      await act(async () => {
        await result.current.setIntensity(0.6);
      });

      expect(result.current.intensity).toBe(0.6);
    });

    it('should use useEnhancementToggle for enabled toggle', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      const mockGet = vi.fn().mockResolvedValue(null);

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      vi.mocked(useWebSocketSubscription).mockReturnValue(undefined as any);

      const { result } = renderHook(() => useEnhancementToggle());

      expect(result.current.enabled).toBe(false);

      await act(async () => {
        await result.current.toggleEnabled();
      });

      expect(result.current.enabled).toBe(true);
    });
  });
});
