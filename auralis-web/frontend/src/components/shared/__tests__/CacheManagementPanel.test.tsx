/**
 * CacheManagementPanel Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for cache management panel component.
 *
 * Test Coverage:
 * - Rendering with loaded data
 * - Loading and error states
 * - Clear all cache functionality
 * - Clear specific track functionality
 * - Refresh statistics
 * - Advanced mode
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import { CacheManagementPanel } from '../CacheManagementPanel';
import * as hooks from '@/hooks/useStandardizedAPI';
import {
  mockCacheStats,
  mockCacheHealth,
  mockUseCacheStats,
  mockUseCacheHealth,
  mockUseStandardizedAPI,
} from './test-utils';

// Mock the hooks
vi.mock('@/hooks/useStandardizedAPI', () => ({
  useCacheStats: vi.fn(),
  useCacheHealth: vi.fn(),
  useStandardizedAPI: vi.fn(),
}));

describe('CacheManagementPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (hooks.useCacheStats as any).mockImplementation(mockUseCacheStats());
    (hooks.useCacheHealth as any).mockImplementation(mockUseCacheHealth());
    (hooks.useStandardizedAPI as any).mockImplementation(mockUseStandardizedAPI());
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  it('should render with cache stats loaded', async () => {
    render(<CacheManagementPanel />);

    await waitFor(() => {
      expect(screen.getByText('Cache Management')).toBeInTheDocument();
    });

    // Check memory gauge
    expect(screen.getByText(/Memory Usage/i)).toBeInTheDocument();
    expect(screen.getByText(/225.0.*MB/)).toBeInTheDocument();
  });

  it('should display tier statistics', async () => {
    render(<CacheManagementPanel />);

    await waitFor(() => {
      expect(screen.getByText('🔥 Tier 1 (Hot Cache)')).toBeInTheDocument();
      expect(screen.getByText('🧊 Tier 2 (Warm Cache)')).toBeInTheDocument();
    });

    // Tier 1 stats
    expect(screen.getByText('4')).toBeInTheDocument(); // chunks
    expect(screen.getByText('6.0 MB')).toBeInTheDocument(); // size
  });

  it('should render loading state', () => {
    (hooks.useCacheStats as any).mockImplementation(() => ({
      data: null,
      loading: true,
      error: null,
      refetch: vi.fn(),
    }));

    render(<CacheManagementPanel />);

    expect(screen.getByText(/Loading cache management/i)).toBeInTheDocument();
  });

  it('should render error state', () => {
    (hooks.useCacheStats as any).mockImplementation(() => ({
      data: null,
      loading: false,
      error: 'Failed to load',
      refetch: vi.fn(),
    }));

    render(<CacheManagementPanel />);

    expect(screen.getByText(/Failed to load cache data/i)).toBeInTheDocument();
  });

  // ============================================================================
  // Clear Cache Tests
  // ============================================================================

  it('should show clear cache button', async () => {
    render(<CacheManagementPanel />);

    await waitFor(() => {
      expect(screen.getByText('🗑️ Clear All Cache')).toBeInTheDocument();
    });
  });

  it('should show confirmation modal when clear cache clicked', async () => {
    render(<CacheManagementPanel />);

    const clearButton = await screen.findByText('🗑️ Clear All Cache');
    fireEvent.click(clearButton);

    await waitFor(() => {
      expect(screen.getByText('Clear All Cache?')).toBeInTheDocument();
    });
  });

  it('should clear cache when confirmation accepted', async () => {
    const mockClearCache = vi.fn().mockResolvedValue(undefined);
    const mockRefetch = vi.fn().mockResolvedValue(undefined);

    (hooks.useStandardizedAPI as any).mockImplementation(() => ({
      refetch: mockClearCache,
      loading: false,
      error: null,
    }));

    (hooks.useCacheStats as any).mockImplementation(() => ({
      data: mockCacheStats,
      loading: false,
      error: null,
      refetch: mockRefetch,
    }));

    render(<CacheManagementPanel />);

    const clearButton = await screen.findByText('🗑️ Clear All Cache');
    fireEvent.click(clearButton);

    const confirmButton = await screen.findByText('Clear All');
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  it('should cancel clear cache when cancelled', async () => {
    render(<CacheManagementPanel />);

    const clearButton = await screen.findByText('🗑️ Clear All Cache');
    fireEvent.click(clearButton);

    const cancelButton = await screen.findByText('Cancel');
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByText('Clear All Cache?')).not.toBeInTheDocument();
    });
  });

  // ============================================================================
  // Refresh Tests
  // ============================================================================

  it('should refresh statistics when refresh button clicked', async () => {
    const mockRefetch = vi.fn().mockResolvedValue(undefined);

    (hooks.useCacheStats as any).mockImplementation(() => ({
      data: mockCacheStats,
      loading: false,
      error: null,
      refetch: mockRefetch,
    }));

    render(<CacheManagementPanel />);

    const refreshButton = await screen.findByText('🔄 Refresh Stats');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Advanced Mode Tests
  // ============================================================================

  it('should show advanced section when enabled', async () => {
    render(<CacheManagementPanel showAdvanced={true} />);

    await waitFor(() => {
      expect(screen.getByText('📋 Per-Track Cache Management')).toBeInTheDocument();
    });
  });

  it('should not show advanced section by default', async () => {
    render(<CacheManagementPanel />);

    await waitFor(() => {
      expect(screen.queryByText('📋 Per-Track Cache Management')).not.toBeInTheDocument();
    });
  });

  it('should show per-track clearing in advanced mode', async () => {
    render(<CacheManagementPanel showAdvanced={true} />);

    await waitFor(() => {
      expect(screen.getByText('📋 Per-Track Cache Management')).toBeInTheDocument();
      expect(screen.getAllByText('Clear').length).toBeGreaterThan(0);
    });
  });

  // ============================================================================
  // Callback Tests
  // ============================================================================

  it('should call onCacheClearRequest callback when cache cleared', async () => {
    const mockCallback = vi.fn();
    const mockClearCache = vi.fn().mockResolvedValue(undefined);
    const mockRefetch = vi.fn().mockResolvedValue(undefined);

    (hooks.useStandardizedAPI as any).mockImplementation(() => ({
      refetch: mockClearCache,
      loading: false,
      error: null,
    }));

    (hooks.useCacheStats as any).mockImplementation(() => ({
      data: mockCacheStats,
      loading: false,
      error: null,
      refetch: mockRefetch,
    }));

    render(
      <CacheManagementPanel
        onCacheClearRequest={mockCallback}
      />
    );

    const clearButton = await screen.findByText('🗑️ Clear All Cache');
    fireEvent.click(clearButton);

    const confirmButton = await screen.findByText('Clear All');
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockCallback).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Disabled State Tests
  // ============================================================================

  it('should disable clear button when cache is empty', async () => {
    (hooks.useCacheStats as any).mockImplementation(() => ({
      data: {
        ...mockCacheStats,
        overall: {
          ...mockCacheStats.overall,
          total_chunks: 0,
        },
      },
      loading: false,
      error: null,
      refetch: vi.fn(),
    }));

    render(<CacheManagementPanel />);

    await waitFor(() => {
      const clearButton = screen.getByText('🗑️ Clear All Cache') as HTMLButtonElement;
      expect(clearButton.disabled).toBe(true);
    });
  });

  it('should disable refresh button during loading', async () => {
    (hooks.useCacheStats as any).mockImplementation(() => ({
      data: mockCacheStats,
      loading: true,
      error: null,
      refetch: vi.fn(),
    }));

    render(<CacheManagementPanel />);

    await waitFor(() => {
      const refreshButton = screen.getByText('🔄 Refresh Stats') as HTMLButtonElement;
      expect(refreshButton.disabled).toBe(true);
    });
  });
});
