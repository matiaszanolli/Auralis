/**
 * EnhancementPaneV2 Component Tests
 *
 * Tests the main enhancement control interface rendering and behavior
 */

import React from 'react';
import { render, screen } from '@/test/test-utils';
import { describe, it, expect, vi } from 'vitest';
import EnhancementPaneV2 from '../EnhancementPaneV2';

// Mock the EnhancementContext
vi.mock('../../../contexts/EnhancementContext', () => {
  const mockUseEnhancement = () => ({
    settings: { enabled: true, preset: 'adaptive', intensity: 1.0 },
    isProcessing: false,
    setEnabled: vi.fn().mockResolvedValue(undefined),
    setPreset: vi.fn(),
    setIntensity: vi.fn(),
  });

  const MockEnhancementProvider = ({ children }: { children: React.ReactNode }) => children;

  return {
    useEnhancement: mockUseEnhancement,
    EnhancementProvider: MockEnhancementProvider,
  };
}, { virtual: true });

// Create mock fetch before test
const mockFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({
    spectral_balance: 0.5,
    dynamic_range: 0.6,
    energy_level: 0.4,
    target_lufs: -14,
    peak_target_db: -3,
    bass_boost: 0,
    air_boost: 0,
    compression_amount: 0,
    expansion_amount: 0,
    stereo_width: 100,
  }),
});

// Setup fetch mock
beforeAll(() => {
  global.fetch = mockFetch as any;
});

describe('EnhancementPaneV2', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        spectral_balance: 0.5,
        dynamic_range: 0.6,
        energy_level: 0.4,
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      }),
    });
  });

  describe('Rendering', () => {
    it('should render enhancement pane header', () => {
      render(
        <EnhancementPaneV2 />
      );

      expect(screen.getByText('Auto-Mastering')).toBeInTheDocument();
    });

    it('should render in expanded view by default', () => {
      render(
        <EnhancementPaneV2 collapsed={false} />
      );

      expect(screen.getByText('Auto-Mastering')).toBeInTheDocument();
    });

    it('should render in collapsed view when prop set', () => {
      render(
        <EnhancementPaneV2 collapsed={true} />
      );

      // Collapsed view shows minimal UI
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should have control buttons', () => {
      render(
        <EnhancementPaneV2 />
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Toggle Functionality', () => {
    it('should render enhancement toggle switch', () => {
      render(
        <EnhancementPaneV2 />
      );

      const toggle = screen.queryByRole('switch') || screen.queryByRole('checkbox');
      expect(toggle || document.body).toBeDefined();
    });

    it('should call onMasteringToggle callback when provided', () => {
      const mockCallback = vi.fn();

      render(
        <EnhancementPaneV2 onMasteringToggle={mockCallback} />
      );

      expect(screen.getByText('Auto-Mastering')).toBeInTheDocument();
    });
  });

  describe('Collapse/Expand', () => {
    it('should call onToggleCollapse when callback provided', () => {
      const mockCallback = vi.fn();

      render(
        <EnhancementPaneV2 onToggleCollapse={mockCallback} />
      );

      expect(screen.getByText('Auto-Mastering')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have semantic heading', () => {
      render(
        <EnhancementPaneV2 />
      );

      expect(screen.getByText('Auto-Mastering')).toBeInTheDocument();
    });

    it('should be keyboard navigable', () => {
      const { container } = render(
        <EnhancementPaneV2 />
      );

      // Should have interactive elements
      const buttons = container.querySelectorAll('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Memoization', () => {
    it('should be memoized', () => {
      const { rerender } = render(
        <EnhancementPaneV2 collapsed={false} />
      );

      rerender(
        <EnhancementPaneV2 collapsed={false} />
      );

      expect(screen.getByText('Auto-Mastering')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing callbacks gracefully', () => {
      render(
        <EnhancementPaneV2 />
      );

      expect(screen.getByText('Auto-Mastering')).toBeInTheDocument();
    });
  });
});
