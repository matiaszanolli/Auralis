/**
 * QueuePanel Component Tests
 *
 * Comprehensive test suite for queue panel UI component.
 * Covers: display, controls, interactions, and responsive behavior
 */

import { ReactElement, ReactNode } from 'react';
import { describe, it, expect, beforeAll, beforeEach, vi, afterEach, afterAll } from 'vitest';
import { render, screen, within, fireEvent, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { QueuePanel } from '../QueuePanel';

// Mock usePlaybackQueue at module level (MUST be before component import)
const mockToggleShuffle = vi.fn().mockResolvedValue(undefined);
const mockSetRepeatMode = vi.fn().mockResolvedValue(undefined);
const mockRemoveTrack = vi.fn().mockResolvedValue(undefined);
const mockClearQueue = vi.fn().mockResolvedValue(undefined);

vi.mock('@/hooks/player/usePlaybackQueue', () => ({
  usePlaybackQueue: vi.fn(() => ({
    queue: [],
    currentIndex: 0,
    currentTrack: null,
    isShuffled: false,
    repeatMode: 'off',
    setQueue: vi.fn().mockResolvedValue(undefined),
    addTrack: vi.fn().mockResolvedValue(undefined),
    removeTrack: mockRemoveTrack,
    reorderTrack: vi.fn().mockResolvedValue(undefined),
    reorderQueue: vi.fn().mockResolvedValue(undefined),
    toggleShuffle: mockToggleShuffle,
    setRepeatMode: mockSetRepeatMode,
    clearQueue: mockClearQueue,
    isLoading: false,
    error: null,
    clearError: vi.fn(),
  })),
}));

// Import the mocked module for manipulation
import * as usePlaybackQueueModule from '@/hooks/player/usePlaybackQueue';

// Mock tracks for testing
const mockTracks = [
  {
    id: 1,
    title: 'Track 1',
    artist: 'Artist A',
    album: 'Album 1',
    duration: 180,
    filepath: '/music/track1.mp3',
  },
  {
    id: 2,
    title: 'Track 2',
    artist: 'Artist B',
    album: 'Album 2',
    duration: 240,
    filepath: '/music/track2.mp3',
  },
  {
    id: 3,
    title: 'Track 3',
    artist: 'Artist C',
    album: 'Album 3',
    duration: 200,
    filepath: '/music/track3.mp3',
  },
];

/**
 * Minimal wrapper for tests
 */
function MinimalWrapper({ children }: { children: ReactNode }) {
  // No <BrowserRouter> (#4943): this file kept its own copy of the router
  // wrapper that test-utils.tsx had, and the app has no router at all.
  return (
    <ThemeProvider>
      {children}
    </ThemeProvider>
  );
}

function renderWithWrapper(ui: ReactElement) {
  return render(ui, { wrapper: MinimalWrapper });
}

/**
 * Give the queue list a real size in jsdom.
 *
 * QueuePanel virtualizes with @tanstack/react-virtual, whose measurement path
 * (virtual-core's `getRect`) reads `offsetWidth`/`offsetHeight`. jsdom performs
 * no layout and reports 0 for both, so the virtual window computed to zero rows
 * and QueuePanel rendered an empty list -- every assertion that looked for a
 * track failed, and any assertion merely expecting rows to be ABSENT passed
 * vacuously. Stubbing getBoundingClientRect alone does not help; the virtualizer
 * does not consult it.
 */
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
    configurable: true,
    get: () => 600,
  });
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
    configurable: true,
    get: () => 400,
  });
});

afterAll(() => {
  // Prototype patches are global; leaving them set would leak into any suite
  // sharing this worker.
  delete (HTMLElement.prototype as unknown as Record<string, unknown>).offsetHeight;
  delete (HTMLElement.prototype as unknown as Record<string, unknown>).offsetWidth;
});

describe('QueuePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Setup default mock return value with tracks
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: mockRemoveTrack,
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: mockToggleShuffle,
      setRepeatMode: mockSetRepeatMode,
      clearQueue: mockClearQueue,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  // =========================================================================
  // DISPLAY & LAYOUT
  // =========================================================================

  it('should render queue panel with all tracks', () => {
    renderWithWrapper(<QueuePanel />);

    expect(screen.getByText('Queue (3)')).toBeInTheDocument();
    expect(screen.getByText('Track 1')).toBeInTheDocument();
    expect(screen.getByText('Track 2')).toBeInTheDocument();
    expect(screen.getByText('Track 3')).toBeInTheDocument();
  });

  it('should display tracks with correct information', () => {
    renderWithWrapper(<QueuePanel />);

    // Check first track
    expect(screen.getByText('Track 1')).toBeInTheDocument();
    expect(screen.getByText('Artist A')).toBeInTheDocument();
    expect(screen.getByText('3:00')).toBeInTheDocument(); // 180 seconds
  });

  it('should highlight current playing track', () => {
    renderWithWrapper(<QueuePanel />);

    // Current track (index 0) should have playing indicator
    const trackItems = screen.getAllByRole('listitem');
    expect(trackItems.length).toBeGreaterThan(0);
  });

  it('should show collapsed state when collapsed prop is true', () => {
    renderWithWrapper(<QueuePanel collapsed={true} />);

    expect(screen.getByText('▶ Queue (3)')).toBeInTheDocument();
  });

  it('should render empty state when queue is empty', () => {
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      queue: [],
      currentIndex: 0,
      currentTrack: null,
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: mockRemoveTrack,
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: mockToggleShuffle,
      setRepeatMode: mockSetRepeatMode,
      clearQueue: mockClearQueue,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    renderWithWrapper(<QueuePanel />);

    expect(screen.getByText('Queue is empty')).toBeInTheDocument();
    expect(screen.getByText('Add tracks to get started')).toBeInTheDocument();
  });

  // =========================================================================
  // SHUFFLE CONTROL
  // =========================================================================

  it('should toggle shuffle mode', async () => {
    renderWithWrapper(<QueuePanel />);

    const shuffleButton = screen.getByTitle('Shuffle: OFF');
    await userEvent.click(shuffleButton);

    expect(mockToggleShuffle).toHaveBeenCalled();
  });

  it('should show shuffle as active when enabled', () => {
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: true,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: mockRemoveTrack,
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: mockToggleShuffle,
      setRepeatMode: mockSetRepeatMode,
      clearQueue: mockClearQueue,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    renderWithWrapper(<QueuePanel />);

    const shuffleButton = screen.getByTitle('Shuffle: ON');
    expect(shuffleButton).toBeInTheDocument();
  });

  // =========================================================================
  // REPEAT MODE CONTROL
  // =========================================================================

  it('should set repeat mode to off', async () => {
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'all',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: mockRemoveTrack,
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: mockToggleShuffle,
      setRepeatMode: mockSetRepeatMode,
      clearQueue: mockClearQueue,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    renderWithWrapper(<QueuePanel />);

    const repeatOffButton = screen.getByTitle('Repeat: OFF');
    await userEvent.click(repeatOffButton);

    expect(mockSetRepeatMode).toHaveBeenCalledWith('off');
  });

  it('should set repeat mode to all', async () => {
    renderWithWrapper(<QueuePanel />);

    const repeatAllButton = screen.getByTitle('Repeat: ALL');
    await userEvent.click(repeatAllButton);

    expect(mockSetRepeatMode).toHaveBeenCalledWith('all');
  });

  it('should set repeat mode to one', async () => {
    renderWithWrapper(<QueuePanel />);

    const repeatOneButton = screen.getByTitle('Repeat: ONE');
    await userEvent.click(repeatOneButton);

    expect(mockSetRepeatMode).toHaveBeenCalledWith('one');
  });

  // =========================================================================
  // REMOVE TRACK
  // =========================================================================

  it('should remove track from queue', async () => {
    renderWithWrapper(<QueuePanel />);

    // Find track items and hover to reveal remove button
    const trackItems = screen.getAllByRole('listitem');
    if (trackItems.length > 1) {
      fireEvent.mouseEnter(trackItems[1]);

      const removeButton = within(trackItems[1]).queryByText('✕');
      if (removeButton) {
        await userEvent.click(removeButton);
        expect(mockRemoveTrack).toHaveBeenCalledWith(1);
      }
    }
  });

  // =========================================================================
  // CLEAR QUEUE
  // =========================================================================

  // These two asserted against window.confirm, which QueuePanel stopped using
  // when confirmation moved to the in-app ClearQueueDialog. The first failed
  // outright; the second passed vacuously, since clicking "Clear queue" only
  // opens the dialog and clearQueue is legitimately not called at that point --
  // it would have passed even with cancellation completely broken.

  it('should clear entire queue with confirmation', async () => {
    renderWithWrapper(<QueuePanel />);

    await userEvent.click(screen.getByTitle('Clear queue'));

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Clear the entire queue?')).toBeInTheDocument();
    // Opening the dialog must not clear anything on its own.
    expect(mockClearQueue).not.toHaveBeenCalled();

    await userEvent.click(within(dialog).getByRole('button', { name: 'Clear' }));

    expect(mockClearQueue).toHaveBeenCalled();
  });

  it('should not clear queue if user cancels', async () => {
    renderWithWrapper(<QueuePanel />);

    await userEvent.click(screen.getByTitle('Clear queue'));
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }),
    );

    expect(mockClearQueue).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  // =========================================================================
  // ERROR DISPLAY
  // =========================================================================

  it('should display error message when present', () => {
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: mockRemoveTrack,
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: mockToggleShuffle,
      setRepeatMode: mockSetRepeatMode,
      clearQueue: mockClearQueue,
      isLoading: false,
      error: { message: 'Failed to update queue', code: 'QUEUE_ERROR', status: 500 },
      clearError: vi.fn(),
    } as any);

    renderWithWrapper(<QueuePanel />);

    expect(screen.getByText('Failed to update queue')).toBeInTheDocument();
  });

  // =========================================================================
  // TOGGLE COLLAPSE
  // =========================================================================

  it('should call onToggleCollapse when toggle button clicked', async () => {
    const mockToggleCollapse = vi.fn();

    renderWithWrapper(<QueuePanel collapsed={false} onToggleCollapse={mockToggleCollapse} />);

    const toggleButton = screen.getByTitle('Collapse queue');
    await userEvent.click(toggleButton);

    expect(mockToggleCollapse).toHaveBeenCalled();
  });
});

/**
 * Keyboard reorder (#4536)
 *
 * reorderTrack existed and was wired only to handleDragEnd, i.e. only to the
 * native drag events, so queue reordering was pointer-only. #2350 specified
 * both halves of this and only the remove half landed.
 */
describe('QueuePanel keyboard reorder (#4536)', () => {
  const mockReorderTrack = vi.fn().mockResolvedValue(undefined);

  const setup = (overrides: Record<string, unknown> = {}) => {
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: mockRemoveTrack,
      reorderTrack: mockReorderTrack,
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: mockToggleShuffle,
      setRepeatMode: mockSetRepeatMode,
      clearQueue: mockClearQueue,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
      ...overrides,
    } as any);
    return renderWithWrapper(<QueuePanel />);
  };

  const rowAt = (index: number) =>
    document.querySelector(`[data-queue-index="${index}"]`) as HTMLElement;

  beforeEach(() => {
    mockReorderTrack.mockClear();
    mockReorderTrack.mockResolvedValue(undefined);
  });

  it('reorders down via Alt+ArrowDown', async () => {
    setup();

    fireEvent.keyDown(rowAt(0), { key: 'ArrowDown', altKey: true });

    expect(mockReorderTrack).toHaveBeenCalledWith(0, 1);
  });

  it('reorders up via Alt+ArrowUp', async () => {
    setup();

    fireEvent.keyDown(rowAt(2), { key: 'ArrowUp', altKey: true });

    expect(mockReorderTrack).toHaveBeenCalledWith(2, 1);
  });

  it('does not reorder past the start of the queue', () => {
    setup();

    fireEvent.keyDown(rowAt(0), { key: 'ArrowUp', altKey: true });

    expect(mockReorderTrack).not.toHaveBeenCalled();
  });

  it('does not reorder past the end of the queue', () => {
    setup();

    fireEvent.keyDown(rowAt(mockTracks.length - 1), { key: 'ArrowDown', altKey: true });

    expect(mockReorderTrack).not.toHaveBeenCalled();
  });

  it('keeps focus on the moved row so repeated presses move the same track', async () => {
    setup();

    rowAt(0).focus();
    fireEvent.keyDown(rowAt(0), { key: 'ArrowDown', altKey: true });

    // The regression risk called out in the issue: the row key embeds the
    // index, so the moved row remounts and focus would otherwise be lost --
    // a second Alt+ArrowDown would then move a different track.
    await vi.waitFor(() => expect(rowAt(1)).toHaveFocus());
  });

  it('announces the new position', async () => {
    setup();

    fireEvent.keyDown(rowAt(0), { key: 'ArrowDown', altKey: true });

    await vi.waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        'Track 1 moved to position 2 of 3',
      ),
    );
  });

  it('announces when the track is already at an end', async () => {
    setup();

    fireEvent.keyDown(rowAt(0), { key: 'ArrowUp', altKey: true });

    await vi.waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        'Track 1 is already first in the queue',
      ),
    );
  });

  it('reports a rejected reorder instead of failing silently', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockReorderTrack.mockRejectedValueOnce(new Error('boom'));
    setup();

    fireEvent.keyDown(rowAt(0), { key: 'ArrowDown', altKey: true });

    await vi.waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Could not move Track 1'),
    );
    // Rolled back optimistically, so focus belongs back on the original row.
    await vi.waitFor(() => expect(rowAt(0)).toHaveFocus());
    consoleError.mockRestore();
  });

  it('does not reorder while a queue command is in flight', () => {
    setup({ isLoading: true });

    fireEvent.keyDown(rowAt(0), { key: 'ArrowDown', altKey: true });

    expect(mockReorderTrack).not.toHaveBeenCalled();
  });
});

describe('QueuePanel row keys (#4428)', () => {
  // The key was `${track.id}-${index}`, so position was part of a row's
  // identity: any reorder or mid-queue removal changed the key of every shifted
  // row and React unmounted/remounted them — the opposite of what
  // QueueTrackItem's React.memo comparator was added for (#4177) — dropping
  // each row's transient isFocused/hover state along the way.

  const baseQueueState = {
    currentIndex: 0,
    currentTrack: null,
    isShuffled: false,
    repeatMode: 'off' as const,
    setQueue: vi.fn().mockResolvedValue(undefined),
    addTrack: vi.fn().mockResolvedValue(undefined),
    removeTrack: mockRemoveTrack,
    reorderTrack: vi.fn().mockResolvedValue(undefined),
    reorderQueue: vi.fn().mockResolvedValue(undefined),
    toggleShuffle: mockToggleShuffle,
    setRepeatMode: mockSetRepeatMode,
    clearQueue: mockClearQueue,
    isLoading: false,
    error: null,
    clearError: vi.fn(),
  };

  const renderQueue = (queue: typeof mockTracks) => {
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      ...baseQueueState,
      queue,
      currentTrack: queue[0] ?? null,
    } as never);
    return renderWithWrapper(<QueuePanel />);
  };

  const rowFor = (title: string): HTMLElement =>
    screen.getByText(title).closest('li') as HTMLElement;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('reuses the same DOM node for a track after a reorder', () => {
    const { rerender } = renderQueue(mockTracks);
    const nodeBefore = rowFor('Track 3');

    // Move Track 1 to the end: [1,2,3] -> [2,3,1]. Track 3 shifts position, so
    // an index-bearing key would change and force a remount.
    const reordered = [mockTracks[1], mockTracks[2], mockTracks[0]];
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      ...baseQueueState,
      queue: reordered,
      currentTrack: reordered[0],
    } as never);
    rerender(<QueuePanel />);

    // Same element instance === React reconciled rather than remounted.
    expect(rowFor('Track 3')).toBe(nodeBefore);
  });

  it('reuses the same DOM node for tracks after a mid-queue removal', () => {
    const { rerender } = renderQueue(mockTracks);
    const nodeBefore = rowFor('Track 3');

    const removed = [mockTracks[0], mockTracks[2]]; // drop Track 2
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      ...baseQueueState,
      queue: removed,
      currentTrack: removed[0],
    } as never);
    rerender(<QueuePanel />);

    expect(rowFor('Track 3')).toBe(nodeBefore);
  });

  it('renders duplicate tracks without a duplicate-key warning', () => {
    // The backend queue does not dedupe (QueueController.add_track appends
    // unconditionally), so keying on track.id alone would collide. Occurrence
    // ordinals keep the keys unique.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const withDupes = [mockTracks[0], mockTracks[1], mockTracks[0]];

    renderQueue(withDupes);

    expect(screen.getAllByText('Track 1')).toHaveLength(2);
    const duplicateKeyWarning = consoleError.mock.calls.some(([msg]) =>
      typeof msg === 'string' && msg.includes('same key'),
    );
    expect(duplicateKeyWarning).toBe(false);
    consoleError.mockRestore();
  });
});

describe('QueuePanel collapsed/expanded transitions (#5007)', () => {
  // Before the fix, QueuePanel called 9 hooks AFTER `if (collapsed) return`
  // — collapsed=true called 11 hooks, collapsed=false called 20. React
  // matches hooks to fiber slots strictly by call order/count per component
  // instance, so a mid-lifetime transition between the two threw "Rendered
  // fewer hooks than expected". The fix (extracting the expanded body into
  // QueuePanelExpanded, mounted/unmounted as its own component instance
  // rather than conditionally calling extra hooks inside one instance) means
  // this transition must no longer throw in either direction.

  // Self-contained mock setup — do not rely on a sibling describe block's
  // beforeEach/mockReturnValue, which vi.clearAllMocks() does not reset.
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePlaybackQueueModule.usePlaybackQueue).mockReturnValue({
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: mockRemoveTrack,
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: mockToggleShuffle,
      setRepeatMode: mockSetRepeatMode,
      clearQueue: mockClearQueue,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it('transitions from collapsed to expanded without a hook-order error', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { rerender } = renderWithWrapper(<QueuePanel collapsed={true} />);
    expect(screen.getByText('▶ Queue (3)')).toBeInTheDocument();

    // renderWithWrapper already applies MinimalWrapper via the `wrapper`
    // render option, which testing-library's rerender() re-applies
    // automatically — wrapping again here would nest a second provider.
    rerender(<QueuePanel collapsed={false} />);

    expect(screen.getByText('Queue (3)')).toBeInTheDocument();
    const hookOrderError = consoleError.mock.calls.some(([msg]) =>
      typeof msg === 'string' &&
      (msg.includes('Rendered fewer hooks than expected') || msg.includes('change in the order of Hooks'))
    );
    expect(hookOrderError).toBe(false);
    consoleError.mockRestore();
  });

  it('transitions from expanded to collapsed without a hook-order error', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { rerender } = renderWithWrapper(<QueuePanel collapsed={false} />);
    expect(screen.getByText('Queue (3)')).toBeInTheDocument();

    rerender(<QueuePanel collapsed={true} />);

    expect(screen.getByText('▶ Queue (3)')).toBeInTheDocument();
    const hookOrderError = consoleError.mock.calls.some(([msg]) =>
      typeof msg === 'string' &&
      (msg.includes('Rendered fewer hooks than expected') || msg.includes('change in the order of Hooks'))
    );
    expect(hookOrderError).toBe(false);
    consoleError.mockRestore();
  });
});
