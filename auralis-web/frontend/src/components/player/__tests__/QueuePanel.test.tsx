/**
 * QueuePanel Component Tests
 *
 * Comprehensive test suite for queue panel UI component.
 * Covers: display, controls, interactions, and responsive behavior
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueuePanel } from '../QueuePanel';
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

describe('QueuePanel', () => {
  beforeEach(() => {
    // Mock usePlaybackQueue hook
    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: vi.fn().mockResolvedValue(undefined),
      clearQueue: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // =========================================================================
  // DISPLAY & LAYOUT
  // =========================================================================

  it('should render queue panel with all tracks', () => {
    render(<QueuePanel />);

    expect(screen.getByText('Queue (3)')).toBeInTheDocument();
    expect(screen.getByText('Track 1')).toBeInTheDocument();
    expect(screen.getByText('Track 2')).toBeInTheDocument();
    expect(screen.getByText('Track 3')).toBeInTheDocument();
  });

  it('should display tracks with correct information', () => {
    render(<QueuePanel />);

    // Check first track
    expect(screen.getByText('Track 1')).toBeInTheDocument();
    expect(screen.getByText('Artist A')).toBeInTheDocument();
    expect(screen.getByText('3:00')).toBeInTheDocument(); // 180 seconds
  });

  it('should highlight current playing track', () => {
    render(<QueuePanel />);

    const trackItems = screen.getAllByTitle(/Track \d - Artist \w/);
    expect(trackItems[0]).toHaveTextContent('▶'); // Playing icon
  });

  it('should show collapsed state when collapsed prop is true', () => {
    const { container } = render(<QueuePanel collapsed={true} />);

    expect(screen.getByText('▶ Queue (3)')).toBeInTheDocument();
    expect(screen.queryByText('Shuffle')).not.toBeInTheDocument();
  });

  it('should render empty state when queue is empty', () => {
    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: [],
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
      queue: [],
      currentIndex: 0,
      currentTrack: null,
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: vi.fn().mockResolvedValue(undefined),
      clearQueue: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<QueuePanel />);

    expect(screen.getByText('Queue is empty')).toBeInTheDocument();
    expect(screen.getByText('Add tracks to get started')).toBeInTheDocument();
  });

  // =========================================================================
  // SHUFFLE CONTROL
  // =========================================================================

  it('should toggle shuffle mode', async () => {
    const mockToggleShuffle = vi.fn().mockResolvedValue(undefined);

    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: mockToggleShuffle,
      setRepeatMode: vi.fn().mockResolvedValue(undefined),
      clearQueue: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<QueuePanel />);

    const shuffleButton = screen.getByTitle('Shuffle: OFF');
    await userEvent.click(shuffleButton);

    expect(mockToggleShuffle).toHaveBeenCalled();
  });

  it('should show shuffle as active when enabled', () => {
    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: true,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: true,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: vi.fn().mockResolvedValue(undefined),
      clearQueue: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<QueuePanel />);

    const shuffleButton = screen.getByTitle('Shuffle: ON');
    expect(shuffleButton).toBeInTheDocument();
  });

  // =========================================================================
  // REPEAT MODE CONTROL
  // =========================================================================

  it('should set repeat mode to off', async () => {
    const mockSetRepeatMode = vi.fn().mockResolvedValue(undefined);

    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'all',
        lastUpdated: Date.now(),
      },
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'all',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: mockSetRepeatMode,
      clearQueue: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<QueuePanel />);

    const repeatOffButton = screen.getByTitle('Repeat: OFF');
    await userEvent.click(repeatOffButton);

    expect(mockSetRepeatMode).toHaveBeenCalledWith('off');
  });

  it('should set repeat mode to all', async () => {
    const mockSetRepeatMode = vi.fn().mockResolvedValue(undefined);

    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: mockSetRepeatMode,
      clearQueue: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<QueuePanel />);

    const repeatAllButton = screen.getByTitle('Repeat: ALL');
    await userEvent.click(repeatAllButton);

    expect(mockSetRepeatMode).toHaveBeenCalledWith('all');
  });

  it('should set repeat mode to one', async () => {
    const mockSetRepeatMode = vi.fn().mockResolvedValue(undefined);

    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: mockSetRepeatMode,
      clearQueue: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<QueuePanel />);

    const repeatOneButton = screen.getByTitle('Repeat: ONE');
    await userEvent.click(repeatOneButton);

    expect(mockSetRepeatMode).toHaveBeenCalledWith('one');
  });

  // =========================================================================
  // REMOVE TRACK
  // =========================================================================

  it('should remove track from queue', async () => {
    const mockRemoveTrack = vi.fn().mockResolvedValue(undefined);

    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
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
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: vi.fn().mockResolvedValue(undefined),
      clearQueue: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<QueuePanel />);

    // Hover over second track to reveal remove button
    const trackItem = screen.getAllByTitle(/Track \d - Artist \w/)[1];
    fireEvent.mouseEnter(trackItem);

    const removeButton = within(trackItem).getByText('✕');
    await userEvent.click(removeButton);

    expect(mockRemoveTrack).toHaveBeenCalledWith(1);
  });

  // =========================================================================
  // CLEAR QUEUE
  // =========================================================================

  it('should clear entire queue with confirmation', async () => {
    const mockClearQueue = vi.fn().mockResolvedValue(undefined);

    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: vi.fn().mockResolvedValue(undefined),
      clearQueue: mockClearQueue,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    // Mock confirm dialog
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<QueuePanel />);

    const clearButton = screen.getByTitle('Clear queue');
    await userEvent.click(clearButton);

    expect(window.confirm).toHaveBeenCalledWith('Clear the entire queue?');
    expect(mockClearQueue).toHaveBeenCalled();
  });

  it('should not clear queue if user cancels', async () => {
    const mockClearQueue = vi.fn().mockResolvedValue(undefined);

    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: vi.fn().mockResolvedValue(undefined),
      clearQueue: mockClearQueue,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    // Mock confirm dialog to return false
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<QueuePanel />);

    const clearButton = screen.getByTitle('Clear queue');
    await userEvent.click(clearButton);

    expect(mockClearQueue).not.toHaveBeenCalled();
  });

  // =========================================================================
  // ERROR DISPLAY
  // =========================================================================

  it('should display error message when present', () => {
    vi.spyOn(usePlaybackQueueModule, 'usePlaybackQueue').mockReturnValue({
      state: {
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      },
      queue: mockTracks,
      currentIndex: 0,
      currentTrack: mockTracks[0],
      isShuffled: false,
      repeatMode: 'off',
      setQueue: vi.fn().mockResolvedValue(undefined),
      addTrack: vi.fn().mockResolvedValue(undefined),
      removeTrack: vi.fn().mockResolvedValue(undefined),
      reorderTrack: vi.fn().mockResolvedValue(undefined),
      reorderQueue: vi.fn().mockResolvedValue(undefined),
      toggleShuffle: vi.fn().mockResolvedValue(undefined),
      setRepeatMode: vi.fn().mockResolvedValue(undefined),
      clearQueue: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
      error: { message: 'Failed to update queue', code: 'QUEUE_ERROR', status: 500 },
      clearError: vi.fn(),
    } as any);

    render(<QueuePanel />);

    expect(screen.getByText('Failed to update queue')).toBeInTheDocument();
  });

  // =========================================================================
  // TOGGLE COLLAPSE
  // =========================================================================

  it('should call onToggleCollapse when toggle button clicked', async () => {
    const mockToggleCollapse = vi.fn();

    render(<QueuePanel collapsed={false} onToggleCollapse={mockToggleCollapse} />);

    const toggleButton = screen.getByTitle('Collapse queue');
    await userEvent.click(toggleButton);

    expect(mockToggleCollapse).toHaveBeenCalled();
  });
});
