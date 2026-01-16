/**
 * useSimilarTracksFormatting Hook Tests
 *
 * Tests for formatting utilities:
 * - Similarity score to color mapping
 * - Duration formatting
 */

import { vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useSimilarTracksFormatting } from '../useSimilarTracksFormatting';

// Mock design system tokens with all required properties for primitives
// The hook uses: semantic.success (90%+), accent.primary (80-90%), accent.secondary (70-80%), text.secondary (<70%)
vi.mock('@/design-system/tokens', () => ({
  tokens: {
    colors: {
      accent: {
        primary: '#7C3AED',    // Used by hook for 80-90% similarity
        secondary: '#999999',  // Used by hook for 70-80% similarity
        success: '#00AA00',
        purple: '#7C3AED',
      },
      text: {
        primary: '#FFFFFF',
        secondary: '#CCCCCC',  // Used by hook for <70% similarity
        disabled: '#666666',
      },
      bg: {
        primary: '#0B1020',
        secondary: '#101729',
        tertiary: '#151D2F',
        elevated: '#1A2338',
        overlay: 'rgba(11, 16, 32, 0.95)',
      },
      border: {
        light: 'rgba(115, 102, 240, 0.12)',
        medium: 'rgba(115, 102, 240, 0.2)',
      },
      semantic: {
        success: '#00AA00',    // Used by hook for 90%+ similarity
        warning: '#F59E0B',
        error: '#EF4444',
        info: '#47D6FF',
      },
    },
    typography: {
      fontSize: {
        xs: '11px',
        sm: '13px',
        md: '16px',
        lg: '18px',
      },
      fontWeight: {
        normal: 400,
        medium: 500,
        semibold: 600,
        bold: 700,
      },
    },
    spacing: {
      xs: '4px',
      sm: '8px',
      md: '12px',
      lg: '16px',
    },
    borderRadius: {
      sm: '8px',
      md: '12px',
      lg: '16px',
      full: '9999px',
    },
    shadows: {
      sm: '0 2px 8px rgba(0, 0, 0, 0.12)',
      md: '0 4px 16px rgba(0, 0, 0, 0.16)',
      lg: '0 8px 24px rgba(0, 0, 0, 0.24)',
    },
  },
}));

describe('useSimilarTracksFormatting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Hook Initialization', () => {
    it('should expose getSimilarityColor and formatDuration utilities', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      expect(result.current.getSimilarityColor).toBeDefined();
      expect(result.current.formatDuration).toBeDefined();
      expect(typeof result.current.getSimilarityColor).toBe('function');
      expect(typeof result.current.formatDuration).toBe('function');
    });
  });

  describe('getSimilarityColor', () => {
    it('should return success color for 90%+ similarity', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.95);

      expect(color).toBe('#00AA00');
    });

    it('should return success color for exactly 0.90 similarity', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.90);

      expect(color).toBe('#00AA00');
    });

    it('should return purple color for 80-89% similarity', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.85);

      expect(color).toBe('#7C3AED');
    });

    it('should return purple color for exactly 0.80 similarity', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.80);

      expect(color).toBe('#7C3AED');
    });

    it('should return secondary color for 70-79% similarity', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.75);

      expect(color).toBe('#999999');
    });

    it('should return secondary color for exactly 0.70 similarity', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.70);

      expect(color).toBe('#999999');
    });

    it('should return gray color for <70% similarity', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.65);

      expect(color).toBe('#CCCCCC');
    });

    it('should handle boundary value just above 90%', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.901);

      expect(color).toBe('#00AA00');
    });

    it('should handle boundary value just below 90%', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.899);

      expect(color).toBe('#7C3AED');
    });

    it('should handle boundary value just below 80%', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.799);

      expect(color).toBe('#999999');
    });

    it('should handle boundary value just below 70%', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.699);

      expect(color).toBe('#CCCCCC');
    });

    it('should handle 0% similarity', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(0.0);

      expect(color).toBe('#CCCCCC');
    });

    it('should handle 100% similarity', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const color = result.current.getSimilarityColor(1.0);

      expect(color).toBe('#00AA00');
    });
  });

  describe('formatDuration', () => {
    it('should format duration correctly', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(185); // 3:05

      expect(formatted).toBe('3:05');
    });

    it('should return empty string for undefined', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(undefined);

      expect(formatted).toBe('');
    });

    it('should return empty string for null', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(null as unknown as number);

      expect(formatted).toBe('');
    });

    it('should return empty string for 0', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(0);

      expect(formatted).toBe('');
    });

    it('should format 60 seconds as "1:00"', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(60);

      expect(formatted).toBe('1:00');
    });

    it('should pad single-digit seconds', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(125); // 2:05

      expect(formatted).toBe('2:05');
    });

    it('should handle large durations', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(3661); // 61:01

      expect(formatted).toBe('61:01');
    });

    it('should truncate decimal seconds', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(125.7); // Should truncate to 125 -> 2:05

      expect(formatted).toBe('2:05');
    });

    it('should format typical 3-minute song', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(180);

      expect(formatted).toBe('3:00');
    });

    it('should format typical 4-minute song', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const formatted = result.current.formatDuration(272); // 4:32

      expect(formatted).toBe('4:32');
    });
  });

  describe('Handler Stability', () => {
    it('should maintain referential equality for getSimilarityColor', () => {
      const { result, rerender } = renderHook(() => useSimilarTracksFormatting());

      const initialHandler = result.current.getSimilarityColor;

      rerender();

      expect(result.current.getSimilarityColor).toBe(initialHandler);
    });

    it('should maintain referential equality for formatDuration', () => {
      const { result, rerender } = renderHook(() => useSimilarTracksFormatting());

      const initialHandler = result.current.formatDuration;

      rerender();

      expect(result.current.formatDuration).toBe(initialHandler);
    });
  });

  describe('Consistency', () => {
    it('should produce consistent results for getSimilarityColor', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const score = 0.85;

      const color1 = result.current.getSimilarityColor(score);
      const color2 = result.current.getSimilarityColor(score);

      expect(color1).toBe(color2);
    });

    it('should produce consistent results for formatDuration', () => {
      const { result } = renderHook(() => useSimilarTracksFormatting());

      const seconds = 185;

      const formatted1 = result.current.formatDuration(seconds);
      const formatted2 = result.current.formatDuration(seconds);

      expect(formatted1).toBe(formatted2);
    });
  });
});
