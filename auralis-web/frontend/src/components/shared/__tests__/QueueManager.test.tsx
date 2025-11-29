/**
 * QueueManager Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for queue manager component with drag-and-drop.
 *
 * Test Coverage:
 * - Queue rendering
 * - Add track
 * - Remove track
 * - Drag-and-drop reordering
 * - Clear queue with confirmation
 * - Current track highlighting
 * - Duration calculations
 * - Empty queue state
 * - Loading states
 * - Error handling
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import { QueueManager } from '../QueueManager';
import * as hooks from '@/hooks/useQueueCommands';
import {
  mockUseQueueCommands,
  mockTracks,
} from './test-utils';

// Mock the hooks
vi.mock('@/hooks/useQueueCommands', () => ({
  useQueueCommands: vi.fn(),
}));

describe('QueueManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (hooks.useQueueCommands as any).mockImplementation(mockUseQueueCommands());
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  it('should render queue title', () => {
    render(<QueueManager />);

    expect(screen.getByText(/Queue/i)).toBeInTheDocument();
  });

  it('should display all tracks in queue', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
      expect(screen.getByText('Track 3')).toBeInTheDocument();
    });
  });

  it('should show track artist names', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      expect(screen.getByText('Artist 1')).toBeInTheDocument();
      expect(screen.getByText('Artist 2')).toBeInTheDocument();
    });
  });

  it('should display track durations', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      expect(screen.getAllByText(/\d:\d{2}/).length).toBeGreaterThan(0);
    });
  });

  // ============================================================================
  // Queue Statistics Tests
  // ============================================================================

  it('should display queue length', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      expect(screen.getByText(/3 tracks/i)).toBeInTheDocument();
    });
  });

  it('should calculate and display total duration', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      // 3 tracks * 180 seconds = 540 seconds = 9:00
      expect(screen.getByText(/Total.*9:00/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Current Track Highlighting Tests
  // ============================================================================

  it('should highlight current track', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      const currentTrack = screen.getByText('Track 1').closest('div');
      expect(currentTrack).toHaveClass('current');
    });
  });

  it('should show current track indicator', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      expect(screen.getByText(/▶/)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Track Removal Tests
  // ============================================================================

  it('should show remove button for each track', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      const removeButtons = screen.getAllByRole('button', { name: /remove/i });
      expect(removeButtons.length).toBe(3);
    });
  });

  it('should remove track when remove button clicked', async () => {
    const mockRemove = vi.fn().mockResolvedValue(undefined);

    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: mockRemove,
      reorder: vi.fn(),
      clear: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<QueueManager />);

    const removeButtons = await screen.findAllByRole('button', { name: /remove/i });
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(mockRemove).toHaveBeenCalledWith(0);
    });
  });

  it('should prevent removing current track', async () => {
    const mockRemove = vi.fn();

    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: mockRemove,
      reorder: vi.fn(),
      clear: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<QueueManager />);

    await waitFor(() => {
      const currentTrackRemoveBtn = screen.getAllByRole('button', { name: /remove/i })[0];
      expect(currentTrackRemoveBtn).toBeDisabled();
    });
  });

  // ============================================================================
  // Drag-and-Drop Tests
  // ============================================================================

  it('should have draggable track items', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      const tracks = screen.getAllByRole('listitem');
      expect(tracks[0]).toHaveAttribute('draggable', 'true');
    });
  });

  it('should reorder track when dragged', async () => {
    const mockReorder = vi.fn().mockResolvedValue(undefined);

    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: vi.fn(),
      reorder: mockReorder,
      clear: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<QueueManager />);

    await waitFor(() => {
      const tracks = screen.getAllByRole('listitem');

      // Simulate drag from index 1 to index 2
      fireEvent.dragStart(tracks[1]);
      fireEvent.dragOver(tracks[2]);
      fireEvent.drop(tracks[2]);
      fireEvent.dragEnd(tracks[1]);
    });

    await waitFor(() => {
      expect(mockReorder).toHaveBeenCalledWith({
        fromIndex: expect.any(Number),
        toIndex: expect.any(Number),
      });
    });
  });

  // ============================================================================
  // Add Track Tests
  // ============================================================================

  it('should show add track button when enabled', () => {
    render(<QueueManager showAddTrack={true} />);

    expect(screen.getByRole('button', { name: /add track/i })).toBeInTheDocument();
  });

  it('should not show add track button by default', () => {
    render(<QueueManager />);

    expect(screen.queryByRole('button', { name: /add track/i })).not.toBeInTheDocument();
  });

  it('should open track selection when add button clicked', async () => {
    render(<QueueManager showAddTrack={true} />);

    const addButton = screen.getByRole('button', { name: /add track/i });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText(/Select a track/i)).toBeInTheDocument();
    });
  });

  it('should add track when selected', async () => {
    const mockAdd = vi.fn().mockResolvedValue(undefined);

    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: mockAdd,
      remove: vi.fn(),
      reorder: vi.fn(),
      clear: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<QueueManager showAddTrack={true} />);

    const addButton = screen.getByRole('button', { name: /add track/i });
    fireEvent.click(addButton);

    await waitFor(() => {
      const selectButton = screen.getByRole('button', { name: /Add/ });
      fireEvent.click(selectButton);
    });

    await waitFor(() => {
      expect(mockAdd).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Clear Queue Tests
  // ============================================================================

  it('should show clear queue button', async () => {
    render(<QueueManager />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /clear queue/i })).toBeInTheDocument();
    });
  });

  it('should show confirmation when clear button clicked', async () => {
    render(<QueueManager />);

    const clearButton = screen.getByRole('button', { name: /clear queue/i });
    fireEvent.click(clearButton);

    await waitFor(() => {
      expect(screen.getByText(/Clear entire queue/i)).toBeInTheDocument();
    });
  });

  it('should clear queue when confirmed', async () => {
    const mockClear = vi.fn().mockResolvedValue(undefined);

    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: vi.fn(),
      reorder: vi.fn(),
      clear: mockClear,
      loading: false,
      error: null,
    }));

    render(<QueueManager />);

    const clearButton = screen.getByRole('button', { name: /clear queue/i });
    fireEvent.click(clearButton);

    const confirmButton = await screen.findByRole('button', { name: /Clear/ });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockClear).toHaveBeenCalled();
    });
  });

  it('should cancel clear when cancelled', async () => {
    const mockClear = vi.fn();

    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: vi.fn(),
      reorder: vi.fn(),
      clear: mockClear,
      loading: false,
      error: null,
    }));

    render(<QueueManager />);

    const clearButton = screen.getByRole('button', { name: /clear queue/i });
    fireEvent.click(clearButton);

    const cancelButton = await screen.findByRole('button', { name: /Cancel/ });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(mockClear).not.toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Empty Queue Tests
  // ============================================================================

  it('should show empty state when no tracks', async () => {
    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: vi.fn(),
      reorder: vi.fn(),
      clear: vi.fn(),
      tracks: [],
      currentIndex: -1,
      loading: false,
      error: null,
    }));

    render(<QueueManager />);

    await waitFor(() => {
      expect(screen.getByText(/Queue is empty/i)).toBeInTheDocument();
    });
  });

  it('should disable clear button when queue is empty', async () => {
    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: vi.fn(),
      reorder: vi.fn(),
      clear: vi.fn(),
      tracks: [],
      currentIndex: -1,
      loading: false,
      error: null,
    }));

    render(<QueueManager />);

    await waitFor(() => {
      const clearButton = screen.getByRole('button', { name: /clear queue/i }) as HTMLButtonElement;
      expect(clearButton.disabled).toBe(true);
    });
  });

  // ============================================================================
  // Loading & Error Tests
  // ============================================================================

  it('should show loading state', async () => {
    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: vi.fn(),
      reorder: vi.fn(),
      clear: vi.fn(),
      tracks: mockTracks(3),
      currentIndex: 0,
      loading: true,
      error: null,
    }));

    render(<QueueManager />);

    expect(screen.getByText(/Loading queue/i)).toBeInTheDocument();
  });

  it('should show error message when error occurs', async () => {
    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: vi.fn(),
      reorder: vi.fn(),
      clear: vi.fn(),
      tracks: mockTracks(3),
      currentIndex: 0,
      loading: false,
      error: 'Failed to load queue',
    }));

    render(<QueueManager />);

    expect(screen.getByText(/Failed to load queue/)).toBeInTheDocument();
  });

  it('should disable operations during loading', async () => {
    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: vi.fn(),
      reorder: vi.fn(),
      clear: vi.fn(),
      tracks: mockTracks(3),
      currentIndex: 0,
      loading: true,
      error: null,
    }));

    render(<QueueManager />);

    await waitFor(() => {
      const removeButtons = screen.queryAllByRole('button', { name: /remove/i });
      removeButtons.forEach((btn) => {
        expect((btn as HTMLButtonElement).disabled).toBe(true);
      });
    });
  });

  // ============================================================================
  // Responsive Tests
  // ============================================================================

  it('should render in compact mode', () => {
    render(<QueueManager compact={true} />);

    // Compact mode may hide some details
    expect(screen.getByText(/Queue/i)).toBeInTheDocument();
  });

  it('should respect max height in normal mode', () => {
    const { container } = render(<QueueManager maxHeight="400px" />);

    const queueContainer = container.querySelector('[data-testid="queue-container"]');
    expect(queueContainer).toHaveStyle({ maxHeight: '400px' });
  });

  // ============================================================================
  // Keyboard Navigation Tests
  // ============================================================================

  it('should remove track when delete key pressed', async () => {
    const mockRemove = vi.fn().mockResolvedValue(undefined);

    (hooks.useQueueCommands as any).mockImplementation(() => ({
      add: vi.fn(),
      remove: mockRemove,
      reorder: vi.fn(),
      clear: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<QueueManager />);

    const tracks = await screen.findAllByRole('listitem');
    fireEvent.keyDown(tracks[1], { key: 'Delete' });

    await waitFor(() => {
      expect(mockRemove).toHaveBeenCalled();
    });
  });
});
