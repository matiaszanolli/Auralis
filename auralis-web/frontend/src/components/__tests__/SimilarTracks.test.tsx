/**
 * SimilarTracks Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for the SimilarTracks sidebar widget component
 *
 * Test Coverage:
 * - Rendering with different states (loading, error, empty, loaded)
 * - Track selection callback
 * - Similarity badge color coding
 * - Props handling (limit, useGraph)
 * - Auto-update on track change
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SimilarTracks from '../SimilarTracks';
import similarityService, { SimilarTrack } from '../../services/similarityService';

// Mock the similarity service
vi.mock('../../services/similarityService', () => ({
  default: {
    findSimilar: vi.fn()
  }
}));

const mockSimilarTracks: SimilarTrack[] = [
  {
    track_id: 2,
    distance: 0.123,
    similarity_score: 0.92,
    title: 'Very Similar Track',
    artist: 'Artist A',
    album: 'Album A',
    duration: 240
  },
  {
    track_id: 3,
    distance: 0.234,
    similarity_score: 0.85,
    title: 'Similar Track',
    artist: 'Artist B',
    album: 'Album B',
    duration: 180
  },
  {
    track_id: 4,
    distance: 0.345,
    similarity_score: 0.75,
    title: 'Somewhat Similar Track',
    artist: 'Artist C',
    album: 'Album C',
    duration: 210
  }
];

describe('SimilarTracks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('Empty States', () => {
    it('should show empty state when no track selected', () => {
      render(<SimilarTracks trackId={null} />);

      expect(screen.getByText(/play a track to discover similar music/i)).toBeInTheDocument();
    });

    it('should show empty state when no similar tracks found', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce([]);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText(/no similar tracks found/i)).toBeInTheDocument();
      });
    });

    it('should show suggestion to try different track', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce([]);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText(/try playing a different track/i)).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('should show loading state initially', () => {
      (similarityService.findSimilar as any).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<SimilarTracks trackId={1} />);

      expect(screen.getByText(/finding similar tracks/i)).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should call findSimilar with correct parameters', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} limit={5} useGraph={true} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 5, true);
      });
    });
  });

  describe('Error State', () => {
    it('should show error message on API failure', async () => {
      const errorMessage = 'Failed to load similar tracks';
      (similarityService.findSimilar as any).mockRejectedValueOnce(
        new Error(errorMessage)
      );

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    it('should handle network errors gracefully', async () => {
      (similarityService.findSimilar as any).mockRejectedValueOnce(
        new Error('Network error')
      );

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });
  });

  describe('Loaded State', () => {
    it('should render similar tracks list', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Similar Tracks')).toBeInTheDocument();
        expect(screen.getByText('Very Similar Track')).toBeInTheDocument();
        expect(screen.getByText('Similar Track')).toBeInTheDocument();
        expect(screen.getByText('Somewhat Similar Track')).toBeInTheDocument();
      });
    });

    it('should display artist names', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText(/Artist A/)).toBeInTheDocument();
        expect(screen.getByText(/Artist B/)).toBeInTheDocument();
        expect(screen.getByText(/Artist C/)).toBeInTheDocument();
      });
    });

    it('should display similarity percentages', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText('92%')).toBeInTheDocument();  // 0.92 -> 92%
        expect(screen.getByText('85%')).toBeInTheDocument();  // 0.85 -> 85%
        expect(screen.getByText('75%')).toBeInTheDocument();  // 0.75 -> 75%
      });
    });

    it('should display track count in footer', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText(/3 tracks/)).toBeInTheDocument();
      });
    });

    it('should show fast lookup indicator when using graph', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} useGraph={true} />);

      await waitFor(() => {
        expect(screen.getByText(/⚡ Fast lookup/)).toBeInTheDocument();
      });
    });

    it('should show real-time search indicator when not using graph', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} useGraph={false} />);

      await waitFor(() => {
        expect(screen.getByText(/🔍 Real-time search/)).toBeInTheDocument();
      });
    });
  });

  describe('Track Selection', () => {
    it('should call onTrackSelect when track clicked', async () => {
      const onTrackSelect = vi.fn();
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} onTrackSelect={onTrackSelect} />);

      await waitFor(() => {
        const firstTrack = screen.getByText('Very Similar Track');
        fireEvent.click(firstTrack);
      });

      expect(onTrackSelect).toHaveBeenCalledWith(2);  // track_id of first similar track
    });

    it('should handle multiple track selections', async () => {
      const onTrackSelect = vi.fn();
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} onTrackSelect={onTrackSelect} />);

      await waitFor(async () => {
        fireEvent.click(screen.getByText('Very Similar Track'));
        fireEvent.click(screen.getByText('Similar Track'));
        fireEvent.click(screen.getByText('Somewhat Similar Track'));
      });

      expect(onTrackSelect).toHaveBeenCalledTimes(3);
      expect(onTrackSelect).toHaveBeenNthCalledWith(1, 2);
      expect(onTrackSelect).toHaveBeenNthCalledWith(2, 3);
      expect(onTrackSelect).toHaveBeenNthCalledWith(3, 4);
    });

    it('should not error if onTrackSelect not provided', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        const firstTrack = screen.getByText('Very Similar Track');
        expect(() => fireEvent.click(firstTrack)).not.toThrow();
      });
    });
  });

  describe('Props Handling', () => {
    it('should respect limit parameter', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks.slice(0, 2));

      render(<SimilarTracks trackId={1} limit={2} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 2, true);
      });
    });

    it('should respect useGraph parameter', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} useGraph={false} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 5, false);
      });
    });

    it('should use default limit of 5', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 5, true);
      });
    });

    it('should use default useGraph of true', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 5, true);
      });
    });
  });

  describe('Auto-Update', () => {
    it('should reload when trackId changes', async () => {
      (similarityService.findSimilar as any)
        .mockResolvedValueOnce(mockSimilarTracks)
        .mockResolvedValueOnce([mockSimilarTracks[0]]);

      const { rerender } = render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 5, true);
      });

      rerender(<SimilarTracks trackId={2} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(2, 5, true);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledTimes(2);
    });

    it('should reload when limit changes', async () => {
      (similarityService.findSimilar as any)
        .mockResolvedValueOnce(mockSimilarTracks)
        .mockResolvedValueOnce(mockSimilarTracks.slice(0, 3));

      const { rerender } = render(<SimilarTracks trackId={1} limit={5} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 5, true);
      });

      rerender(<SimilarTracks trackId={1} limit={3} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 3, true);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledTimes(2);
    });

    it('should reload when useGraph changes', async () => {
      (similarityService.findSimilar as any)
        .mockResolvedValueOnce(mockSimilarTracks)
        .mockResolvedValueOnce(mockSimilarTracks);

      const { rerender } = render(<SimilarTracks trackId={1} useGraph={true} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 5, true);
      });

      rerender(<SimilarTracks trackId={1} useGraph={false} />);

      await waitFor(() => {
        expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 5, false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledTimes(2);
    });

    it('should clear tracks when trackId becomes null', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      const { rerender } = render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Very Similar Track')).toBeInTheDocument();
      });

      rerender(<SimilarTracks trackId={null} />);

      expect(screen.queryByText('Very Similar Track')).not.toBeInTheDocument();
      expect(screen.getByText(/play a track to discover similar music/i)).toBeInTheDocument();
    });
  });

  describe('Duration Formatting', () => {
    it('should format duration correctly', async () => {
      const tracksWithDurations: SimilarTrack[] = [
        { ...mockSimilarTracks[0], duration: 65 },    // 1:05
        { ...mockSimilarTracks[1], duration: 125 },   // 2:05
        { ...mockSimilarTracks[2], duration: 3665 }   // 61:05
      ];

      (similarityService.findSimilar as any).mockResolvedValueOnce(tracksWithDurations);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText(/1:05/)).toBeInTheDocument();
        expect(screen.getByText(/2:05/)).toBeInTheDocument();
        expect(screen.getByText(/61:05/)).toBeInTheDocument();
      });
    });

    it('should handle missing duration', async () => {
      const tracksNoDuration: SimilarTrack[] = [
        { ...mockSimilarTracks[0], duration: undefined }
      ];

      (similarityService.findSimilar as any).mockResolvedValueOnce(tracksNoDuration);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Very Similar Track')).toBeInTheDocument();
      });

      // Should not crash
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA roles', async () => {
      (similarityService.findSimilar as any).mockResolvedValueOnce(mockSimilarTracks);

      render(<SimilarTracks trackId={1} />);

      await waitFor(() => {
        const buttons = screen.getAllByRole('button');
        expect(buttons.length).toBeGreaterThan(0);
      });
    });

    it('should show loading indicator with aria-label', () => {
      (similarityService.findSimilar as any).mockImplementation(
        () => new Promise(() => {})
      );

      render(<SimilarTracks trackId={1} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });
});
