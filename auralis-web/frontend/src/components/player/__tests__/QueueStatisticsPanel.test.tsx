/**
 * QueueStatisticsPanel Component Tests
 *
 * Comprehensive test suite for queue statistics display component.
 * Covers: rendering, statistics display, quality assessment, interactions
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueueStatisticsPanel } from '../QueueStatisticsPanel';
import * as usePlaybackQueueModule from '@/hooks/player/usePlaybackQueue';
import * as useQueueStatisticsModule from '@/hooks/player/useQueueStatistics';

// Mock tracks for testing
const mockTracks = [
  {
    id: 1,
    title: 'Bohemian Rhapsody',
    artist: 'Queen',
    album: 'A Night at the Opera',
    duration: 354,
    filepath: '/music/queen/bohemian.mp3',
  },
  {
    id: 2,
    title: 'Stairway to Heaven',
    artist: 'Led Zeppelin',
    album: 'Led Zeppelin IV',
    duration: 482,
    filepath: '/music/ledzeppelin/stairway.flac',
  },
  {
    id: 3,
    title: 'Imagine',
    artist: 'John Lennon',
    album: 'Imagine',
    duration: 183,
    filepath: '/music/johnlennon/imagine.mp3',
  },
  {
    id: 4,
    title: 'Hotel California',
    artist: 'Eagles',
    album: 'Hotel California',
    duration: 391,
    filepath: '/music/eagles/hotel.mp3',
  },
  {
    id: 5,
    title: 'Perfect',
    artist: 'Ed Sheeran',
    album: 'Divide',
    duration: 263,
    filepath: '/music/edsheeran/perfect.mp3',
  },
];

describe('QueueStatisticsPanel', () => {
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
      setQueue: vi.fn(),
      addTrack: vi.fn(),
      removeTrack: vi.fn(),
      reorderTrack: vi.fn(),
      reorderQueue: vi.fn(),
      toggleShuffle: vi.fn(),
      setRepeatMode: vi.fn(),
      clearQueue: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    // Mock useQueueStatistics hook
    vi.spyOn(useQueueStatisticsModule, 'useQueueStatistics').mockReturnValue({
      stats: {
        trackCount: 5,
        uniqueArtists: 5,
        uniqueAlbums: 5,
        totalDuration: 1673,
        averageDuration: 334.6,
        minDuration: 183,
        maxDuration: 482,
        medianDuration: 354,
        genres: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        artists: {
          mode: 'Queen',
          least: 'Ed Sheeran',
          unique: 5,
          distribution: new Map([
            ['Queen', 1],
            ['Led Zeppelin', 1],
            ['John Lennon', 1],
            ['Eagles', 1],
            ['Ed Sheeran', 1],
          ]),
        },
        albums: {
          mode: null,
          least: null,
          unique: 5,
          distribution: new Map(),
        },
        formats: {
          mode: 'mp3',
          least: 'flac',
          unique: 2,
          distribution: new Map([
            ['mp3', 4],
            ['flac', 1],
          ]),
        },
        isEmpty: false,
        estimatedPlayTime: '27m 53s',
      },
      topArtists: [
        { value: 'Queen', count: 1, percentage: 20 },
        { value: 'Led Zeppelin', count: 1, percentage: 20 },
        { value: 'John Lennon', count: 1, percentage: 20 },
        { value: 'Eagles', count: 1, percentage: 20 },
        { value: 'Ed Sheeran', count: 1, percentage: 20 },
      ],
      topAlbums: [
        { value: 'A Night at the Opera', count: 1, percentage: 20 },
        { value: 'Led Zeppelin IV', count: 1, percentage: 20 },
      ],
      topFormats: [
        { value: 'mp3', count: 4, percentage: 80 },
        { value: 'flac', count: 1, percentage: 20 },
      ],
      genres: [],
      qualityRating: {
        rating: 'good',
        issues: [],
      },
      isEmpty: false,
      getDistributionPercentages: vi.fn(),
      compareWith: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // =========================================================================
  // DISPLAY & LAYOUT
  // =========================================================================

  it('should not render when collapsed is true', () => {
    render(<QueueStatisticsPanel collapsed={true} onToggleCollapse={() => {}} />);

    expect(screen.queryByText('Queue Statistics')).not.toBeInTheDocument();
  });

  it('should render statistics panel when collapsed is false', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('Queue Statistics')).toBeInTheDocument();
  });

  it('should display collapsed button when collapsed', () => {
    render(<QueueStatisticsPanel collapsed={true} onToggleCollapse={() => {}} />);

    expect(screen.getByText('📊 Stats')).toBeInTheDocument();
  });

  it('should display empty state when queue is empty', () => {
    vi.spyOn(useQueueStatisticsModule, 'useQueueStatistics').mockReturnValue({
      stats: {
        trackCount: 0,
        uniqueArtists: 0,
        uniqueAlbums: 0,
        totalDuration: 0,
        averageDuration: 0,
        minDuration: 0,
        maxDuration: 0,
        medianDuration: 0,
        genres: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        artists: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        albums: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        formats: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        isEmpty: true,
        estimatedPlayTime: '0m',
      },
      topArtists: [],
      topAlbums: [],
      topFormats: [],
      genres: [],
      qualityRating: {
        rating: 'poor',
        issues: ['Queue is empty'],
      },
      isEmpty: true,
      getDistributionPercentages: vi.fn(),
      compareWith: vi.fn(),
    });

    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('No queue to analyze')).toBeInTheDocument();
  });

  // =========================================================================
  // SUMMARY SECTION
  // =========================================================================

  it('should display track count in summary', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('5')).toBeInTheDocument(); // track count
  });

  it('should display estimated play time', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('27m 53s')).toBeInTheDocument();
  });

  it('should display unique artists count', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    // Check both the label and value appear
    expect(screen.getByText('Artists')).toBeInTheDocument();
  });

  it('should display unique albums count', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('Albums')).toBeInTheDocument();
  });

  // =========================================================================
  // DURATION ANALYSIS
  // =========================================================================

  it('should display duration analysis section', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('Duration Analysis')).toBeInTheDocument();
  });

  it('should display min, max, average, and median durations', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('Min')).toBeInTheDocument();
    expect(screen.getByText('Max')).toBeInTheDocument();
    expect(screen.getByText('Average')).toBeInTheDocument();
    expect(screen.getByText('Median')).toBeInTheDocument();
  });

  // =========================================================================
  // TOP ITEMS
  // =========================================================================

  it('should display top artists section', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('Top Artists')).toBeInTheDocument();
  });

  it('should display top artists with names', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('Queen')).toBeInTheDocument();
    expect(screen.getByText('Led Zeppelin')).toBeInTheDocument();
  });

  it('should display artist rankings', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    // Should have ranking badges like #1, #2, etc.
    const rankings = screen.getAllByText(/#\d/);
    expect(rankings.length).toBeGreaterThan(0);
  });

  it('should display top albums section', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('Top Albums')).toBeInTheDocument();
  });

  it('should display top formats section', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('File Formats')).toBeInTheDocument();
  });

  // =========================================================================
  // QUALITY ASSESSMENT
  // =========================================================================

  it('should display quality assessment section', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('Quality Assessment')).toBeInTheDocument();
  });

  it('should display quality rating badge', () => {
    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('GOOD')).toBeInTheDocument();
  });

  it('should display quality issues', () => {
    vi.spyOn(useQueueStatisticsModule, 'useQueueStatistics').mockReturnValue({
      stats: {
        trackCount: 5,
        uniqueArtists: 1,
        uniqueAlbums: 1,
        totalDuration: 1673,
        averageDuration: 334.6,
        minDuration: 183,
        maxDuration: 482,
        medianDuration: 354,
        genres: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        artists: {
          mode: 'Queen',
          least: 'Queen',
          unique: 1,
          distribution: new Map([['Queen', 5]]),
        },
        albums: {
          mode: null,
          least: null,
          unique: 1,
          distribution: new Map(),
        },
        formats: {
          mode: 'mp3',
          least: 'mp3',
          unique: 1,
          distribution: new Map([['mp3', 5]]),
        },
        isEmpty: false,
        estimatedPlayTime: '27m 53s',
      },
      topArtists: [{ value: 'Queen', count: 5, percentage: 100 }],
      topAlbums: [],
      topFormats: [{ value: 'mp3', count: 5, percentage: 100 }],
      genres: [],
      qualityRating: {
        rating: 'fair',
        issues: ['Low artist diversity (consider adding more variety)'],
      },
      isEmpty: false,
      getDistributionPercentages: vi.fn(),
      compareWith: vi.fn(),
    });

    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText(/Low artist diversity/)).toBeInTheDocument();
  });

  // =========================================================================
  // INTERACTIONS
  // =========================================================================

  it('should call onToggleCollapse when collapse button is clicked', async () => {
    const mockToggle = vi.fn();
    const user = userEvent.setup();

    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={mockToggle} />
    );

    const collapseButton = screen.getByLabelText('Collapse statistics panel');
    await user.click(collapseButton);

    expect(mockToggle).toHaveBeenCalled();
  });

  it('should call onToggleCollapse when expand button is clicked', async () => {
    const mockToggle = vi.fn();
    const user = userEvent.setup();

    render(
      <QueueStatisticsPanel collapsed={true} onToggleCollapse={mockToggle} />
    );

    const expandButton = screen.getByLabelText('Expand statistics panel');
    await user.click(expandButton);

    expect(mockToggle).toHaveBeenCalled();
  });

  // =========================================================================
  // EXCELLENT RATING
  // =========================================================================

  it('should display excellent quality rating', () => {
    vi.spyOn(useQueueStatisticsModule, 'useQueueStatistics').mockReturnValue({
      stats: {
        trackCount: 10,
        uniqueArtists: 8,
        uniqueAlbums: 10,
        totalDuration: 3000,
        averageDuration: 300,
        minDuration: 200,
        maxDuration: 400,
        medianDuration: 300,
        genres: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        artists: {
          mode: null,
          least: null,
          unique: 8,
          distribution: new Map(),
        },
        albums: {
          mode: null,
          least: null,
          unique: 10,
          distribution: new Map(),
        },
        formats: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        isEmpty: false,
        estimatedPlayTime: '50m',
      },
      topArtists: [
        { value: 'Artist 1', count: 2, percentage: 20 },
        { value: 'Artist 2', count: 2, percentage: 20 },
      ],
      topAlbums: [],
      topFormats: [],
      genres: [],
      qualityRating: {
        rating: 'excellent',
        issues: [],
      },
      isEmpty: false,
      getDistributionPercentages: vi.fn(),
      compareWith: vi.fn(),
    });

    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('EXCELLENT')).toBeInTheDocument();
  });

  // =========================================================================
  // POOR RATING
  // =========================================================================

  it('should display poor quality rating', () => {
    vi.spyOn(useQueueStatisticsModule, 'useQueueStatistics').mockReturnValue({
      stats: {
        trackCount: 1,
        uniqueArtists: 0,
        uniqueAlbums: 0,
        totalDuration: 5,
        averageDuration: 5,
        minDuration: 5,
        maxDuration: 5,
        medianDuration: 5,
        genres: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        artists: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        albums: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        formats: {
          mode: null,
          least: null,
          unique: 0,
          distribution: new Map(),
        },
        isEmpty: false,
        estimatedPlayTime: '5s',
      },
      topArtists: [],
      topAlbums: [],
      topFormats: [],
      genres: [],
      qualityRating: {
        rating: 'poor',
        issues: ['Very short tracks detected (5s minimum)'],
      },
      isEmpty: false,
      getDistributionPercentages: vi.fn(),
      compareWith: vi.fn(),
    });

    render(
      <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
    );

    expect(screen.getByText('POOR')).toBeInTheDocument();
  });
});
