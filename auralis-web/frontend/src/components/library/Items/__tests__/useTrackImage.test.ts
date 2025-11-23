/**
 * useTrackImage Hook Tests
 *
 * Tests for album art thumbnail display:
 * - Image loading state
 * - Image error fallback
 */

import { vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTrackImage } from '../useTrackImage';

describe('useTrackImage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Hook Initialization', () => {
    it('should initialize with imageError false', () => {
      const { result } = renderHook(() => useTrackImage());

      expect(result.current.imageError).toBe(false);
    });
  });

  describe('handleImageError', () => {
    it('should set imageError to true', () => {
      const { result } = renderHook(() => useTrackImage());

      expect(result.current.imageError).toBe(false);

      act(() => {
        result.current.handleImageError();
      });

      expect(result.current.imageError).toBe(true);
    });
  });

  describe('shouldShowImage', () => {
    it('should return true when albumArt provided and no error', () => {
      const { result } = renderHook(() => useTrackImage());

      const shouldShow = result.current.shouldShowImage('http://example.com/art.jpg');

      expect(shouldShow).toBe(true);
    });

    it('should return false when imageError is true', () => {
      const { result } = renderHook(() => useTrackImage());

      act(() => {
        result.current.handleImageError();
      });

      const shouldShow = result.current.shouldShowImage('http://example.com/art.jpg');

      expect(shouldShow).toBe(false);
    });

    it('should return false when albumArt is undefined', () => {
      const { result } = renderHook(() => useTrackImage());

      const shouldShow = result.current.shouldShowImage(undefined);

      expect(shouldShow).toBe(false);
    });

    it('should return false when albumArt is empty string', () => {
      const { result } = renderHook(() => useTrackImage());

      const shouldShow = result.current.shouldShowImage('');

      expect(shouldShow).toBe(false);
    });
  });

  describe('Handler Stability', () => {
    it('should maintain referential equality for handleImageError', () => {
      const { result, rerender } = renderHook(() => useTrackImage());

      const initialHandler = result.current.handleImageError;

      rerender();

      expect(result.current.handleImageError).toBe(initialHandler);
    });

    it('should maintain referential equality for shouldShowImage', () => {
      const { result, rerender } = renderHook(() => useTrackImage());

      const initialShouldShow = result.current.shouldShowImage;

      rerender();

      expect(result.current.shouldShowImage).toBe(initialShouldShow);
    });
  });

  describe('Multiple Image Loads', () => {
    it('should handle sequential image errors', () => {
      const { result } = renderHook(() => useTrackImage());

      // First image
      expect(result.current.shouldShowImage('http://example.com/art1.jpg')).toBe(true);

      act(() => {
        result.current.handleImageError();
      });

      // After error, no image shown
      expect(result.current.shouldShowImage('http://example.com/art2.jpg')).toBe(false);

      // Once error flag is set, it persists
      expect(result.current.imageError).toBe(true);
    });

    it('should hide different images once error occurs', () => {
      const { result } = renderHook(() => useTrackImage());

      const image1 = 'http://example.com/art1.jpg';
      const image2 = 'http://example.com/art2.jpg';

      expect(result.current.shouldShowImage(image1)).toBe(true);
      expect(result.current.shouldShowImage(image2)).toBe(true);

      act(() => {
        result.current.handleImageError();
      });

      // Both images hidden after error
      expect(result.current.shouldShowImage(image1)).toBe(false);
      expect(result.current.shouldShowImage(image2)).toBe(false);
    });
  });

  describe('shouldShowImage Dependencies', () => {
    it('should update result when imageError state changes', () => {
      const { result } = renderHook(() => useTrackImage());

      const testImage = 'http://example.com/art.jpg';

      // Before error
      expect(result.current.shouldShowImage(testImage)).toBe(true);

      // After error
      act(() => {
        result.current.handleImageError();
      });

      expect(result.current.shouldShowImage(testImage)).toBe(false);
    });
  });
});
