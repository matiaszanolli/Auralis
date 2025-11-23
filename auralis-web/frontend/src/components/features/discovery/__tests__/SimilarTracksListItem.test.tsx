/**
 * SimilarTracksListItem Component Tests
 *
 * Tests for individual track row:
 * - Track information display
 * - Similarity score badge
 * - Click handling
 * - Divider display
 */

import { vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { SimilarTracksListItem } from '../SimilarTracksListItem';
import { SimilarTrack } from '../../services/similarityService';

describe('SimilarTracksListItem', () => {
  const mockTrack: SimilarTrack = {
    id: 1,
    title: 'Similar Track',
    artist: 'Similar Artist',
    duration: 240,
    similarity_score: 0.95,
  };

  const mockOnClick = vi.fn();
  const mockGetSimilarityColor = vi.fn(() => '#667eea');
  const mockFormatDuration = vi.fn(() => '4:00');

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Track Information Display', () => {
    it('should display track title', () => {
      render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      expect(screen.getByText('Similar Track')).toBeInTheDocument();
    });

    it('should display track artist', () => {
      render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      expect(screen.getByText(/Similar Artist/)).toBeInTheDocument();
    });

    it('should display formatted duration', () => {
      render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      expect(mockFormatDuration).toHaveBeenCalledWith(240);
      expect(screen.getByText(/4:00/)).toBeInTheDocument();
    });

    it('should handle missing duration', () => {
      const trackWithoutDuration = { ...mockTrack, duration: undefined };

      render(
        <SimilarTracksListItem
          track={trackWithoutDuration}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      expect(mockFormatDuration).not.toHaveBeenCalled();
    });
  });

  describe('Similarity Score Display', () => {
    it('should display similarity score as percentage', () => {
      render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      expect(screen.getByText('95%')).toBeInTheDocument();
    });

    it('should call getSimilarityColor with score', () => {
      render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      expect(mockGetSimilarityColor).toHaveBeenCalledWith(0.95);
    });

    it('should display tooltip with decimal similarity', () => {
      render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      const chip = screen.getByText('95%');
      expect(chip).toBeInTheDocument();
    });

    it('should handle different similarity scores', () => {
      const scores = [0.50, 0.75, 0.90, 0.99];

      scores.forEach((score) => {
        const track = { ...mockTrack, similarity_score: score };
        const { unmount } = render(
          <SimilarTracksListItem
            track={track}
            index={0}
            totalCount={1}
            onClick={mockOnClick}
            getSimilarityColor={mockGetSimilarityColor}
            formatDuration={mockFormatDuration}
          />
        );

        const expectedPercent = `${Math.round(score * 100)}%`;
        expect(screen.getByText(expectedPercent)).toBeInTheDocument();
        unmount();
      });
    });
  });

  describe('Click Handling', () => {
    it('should call onClick with track when clicked', () => {
      render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      const button = screen.getByRole('button');
      button.click();

      expect(mockOnClick).toHaveBeenCalledWith(mockTrack);
    });

    it('should handle multiple clicks', () => {
      render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      const button = screen.getByRole('button');
      button.click();
      button.click();
      button.click();

      expect(mockOnClick).toHaveBeenCalledTimes(3);
    });
  });

  describe('Divider Display', () => {
    it('should display divider when not last item', () => {
      const { container } = render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={5}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      const divider = container.querySelector('hr');
      expect(divider).toBeInTheDocument();
    });

    it('should not display divider when last item', () => {
      const { container } = render(
        <SimilarTracksListItem
          track={mockTrack}
          index={4}
          totalCount={5}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      const divider = container.querySelector('hr');
      expect(divider).not.toBeInTheDocument();
    });

    it('should not display divider when single item', () => {
      const { container } = render(
        <SimilarTracksListItem
          track={mockTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      const divider = container.querySelector('hr');
      expect(divider).not.toBeInTheDocument();
    });
  });

  describe('Different Track Data', () => {
    it('should handle tracks with special characters', () => {
      const specialTrack: SimilarTrack = {
        id: 2,
        title: "Song & Artist's Track (Remix)",
        artist: 'Artist / Collaborator',
        duration: 300,
        similarity_score: 0.88,
      };

      render(
        <SimilarTracksListItem
          track={specialTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      expect(screen.getByText("Song & Artist's Track (Remix)")).toBeInTheDocument();
      expect(screen.getByText(/Artist \/ Collaborator/)).toBeInTheDocument();
    });

    it('should handle long track titles', () => {
      const longTrack: SimilarTrack = {
        id: 3,
        title: 'This is a very long track title that might wrap to multiple lines in the UI',
        artist: 'Test Artist',
        duration: 250,
        similarity_score: 0.92,
      };

      render(
        <SimilarTracksListItem
          track={longTrack}
          index={0}
          totalCount={1}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      expect(screen.getByText(/This is a very long track title/)).toBeInTheDocument();
    });
  });

  describe('Props Integration', () => {
    it('should use all provided props correctly', () => {
      const customTrack: SimilarTrack = {
        id: 99,
        title: 'Custom Track',
        artist: 'Custom Artist',
        duration: 180,
        similarity_score: 0.85,
      };

      render(
        <SimilarTracksListItem
          track={customTrack}
          index={2}
          totalCount={10}
          onClick={mockOnClick}
          getSimilarityColor={mockGetSimilarityColor}
          formatDuration={mockFormatDuration}
        />
      );

      expect(screen.getByText('Custom Track')).toBeInTheDocument();
      expect(mockGetSimilarityColor).toHaveBeenCalledWith(0.85);
      expect(mockFormatDuration).toHaveBeenCalledWith(180);
      expect(mockOnClick).not.toHaveBeenCalled();

      // Now click
      const button = screen.getByRole('button');
      button.click();
      expect(mockOnClick).toHaveBeenCalledWith(customTrack);
    });
  });
});
