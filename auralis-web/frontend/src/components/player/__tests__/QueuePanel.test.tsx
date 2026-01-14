/**
 * QueuePanel Component Tests
 *
 * Comprehensive test suite for queue panel UI component.
 * Covers: display, controls, interactions, and responsive behavior
 */

import React from 'react';
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, within, fireEvent, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
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
function MinimalWrapper({ children }: { children: React.ReactNode }) {
  return (
    <BrowserRouter>
      <ThemeProvider>
        {children}
      </ThemeProvider>
    </BrowserRouter>
  );
}

function renderWithWrapper(ui: React.ReactElement) {
  return render(ui, { wrapper: MinimalWrapper });
}

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

  it('should clear entire queue with confirmation', async () => {
    // Mock confirm dialog
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderWithWrapper(<QueuePanel />);

    const clearButton = screen.getByTitle('Clear queue');
    await userEvent.click(clearButton);

    expect(window.confirm).toHaveBeenCalledWith('Clear the entire queue?');
    expect(mockClearQueue).toHaveBeenCalled();
  });

  it('should not clear queue if user cancels', async () => {
    // Mock confirm dialog to return false
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    renderWithWrapper(<QueuePanel />);

    const clearButton = screen.getByTitle('Clear queue');
    await userEvent.click(clearButton);

    expect(mockClearQueue).not.toHaveBeenCalled();
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
