/**
 * SimilarityVisualization Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for the SimilarityVisualization analysis component
 *
 * Test Coverage:
 * - Rendering with different states (loading, error, empty, loaded)
 * - Overall similarity score display
 * - Top differences highlighting
 * - All dimensions accordion
 * - Value formatting (%, dB, BPM, etc.)
 * - Props handling
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SimilarityVisualization from '../SimilarityVisualization';
import similarityService, { SimilarityExplanation } from '../../services/similarityService';

// Mock the similarity service
vi.mock('../../services/similarityService', () => ({
  default: {
    explainSimilarity: vi.fn()
  }
}));

const mockExplanation: SimilarityExplanation = {
  track_id1: 1,
  track_id2: 2,
  distance: 0.456,
  similarity_score: 0.85,
  top_differences: [
    {
      dimension: 'bass_pct',
      contribution: 0.125,
      value1: 45.2,
      value2: 60.1,
      difference: 14.9
    },
    {
      dimension: 'lufs',
      contribution: 0.102,
      value1: -14.3,
      value2: -12.1,
      difference: 2.2
    },
    {
      dimension: 'tempo_bpm',
      contribution: 0.089,
      value1: 120,
      value2: 140,
      difference: 20
    }
  ],
  all_contributions: [
    { dimension: 'bass_pct', contribution: 0.125 },
    { dimension: 'lufs', contribution: 0.102 },
    { dimension: 'tempo_bpm', contribution: 0.089 },
    { dimension: 'crest_db', contribution: 0.045 },
    { dimension: 'stereo_width', contribution: 0.023 }
  ]
};

describe('SimilarityVisualization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('Empty States', () => {
    it('should show empty state when no tracks selected', () => {
      render(<SimilarityVisualization trackId1={null} trackId2={null} />);

      expect(screen.getByText(/select two tracks to compare/i)).toBeInTheDocument();
    });

    it('should show empty state when only one track selected', () => {
      render(<SimilarityVisualization trackId1={1} trackId2={null} />);

      expect(screen.getByText(/select two tracks to compare/i)).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should show loading state initially', () => {
      (similarityService.explainSimilarity as any).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      expect(screen.getByText(/analyzing similarity/i)).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should call explainSimilarity with correct parameters', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} topN={5} />);

      await waitFor(() => {
        expect(similarityService.explainSimilarity).toHaveBeenCalledWith(1, 2, 5);
      });
    });
  });

  describe('Error State', () => {
    it('should show error message on API failure', async () => {
      const errorMessage = 'Failed to load explanation';
      (similarityService.explainSimilarity as any).mockRejectedValueOnce(
        new Error(errorMessage)
      );

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    it('should handle network errors gracefully', async () => {
      (similarityService.explainSimilarity as any).mockRejectedValueOnce(
        new Error('Network error')
      );

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });
  });

  describe('Overall Similarity Score', () => {
    it('should display similarity percentage', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('85%')).toBeInTheDocument();  // 0.85 -> 85%
      });
    });

    it('should display similarity level badge', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('Similar')).toBeInTheDocument();  // 80-90% = Similar
      });
    });

    it('should display distance value', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/Distance: 0.4560/)).toBeInTheDocument();
      });
    });

    it('should show "Very Similar" for 90%+ scores', async () => {
      const highScoreExplanation = { ...mockExplanation, similarity_score: 0.95 };
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(highScoreExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('Very Similar')).toBeInTheDocument();
      });
    });

    it('should show "Somewhat Similar" for 70-80% scores', async () => {
      const mediumScoreExplanation = { ...mockExplanation, similarity_score: 0.75 };
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mediumScoreExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('Somewhat Similar')).toBeInTheDocument();
      });
    });

    it('should show "Different" for <60% scores', async () => {
      const lowScoreExplanation = { ...mockExplanation, similarity_score: 0.50 };
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(lowScoreExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('Different')).toBeInTheDocument();
      });
    });
  });

  describe('Top Differences', () => {
    it('should display top differences section', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('Top Differences')).toBeInTheDocument();
      });
    });

    it('should display dimension names formatted correctly', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('Bass Pct')).toBeInTheDocument();  // bass_pct -> Bass Pct
        expect(screen.getByText('Lufs')).toBeInTheDocument();       // lufs -> Lufs
        expect(screen.getByText('Tempo Bpm')).toBeInTheDocument();  // tempo_bpm -> Tempo Bpm
      });
    });

    it('should display contribution percentages', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('12.5% impact')).toBeInTheDocument();  // 0.125 -> 12.5%
        expect(screen.getByText('10.2% impact')).toBeInTheDocument();  // 0.102 -> 10.2%
        expect(screen.getByText('8.9% impact')).toBeInTheDocument();   // 0.089 -> 8.9%
      });
    });

    it('should display formatted values for percentage dimensions', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/Track 1: 45.2%/)).toBeInTheDocument();
        expect(screen.getByText(/Track 2: 60.1%/)).toBeInTheDocument();
      });
    });

    it('should display formatted values for dB dimensions', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/Track 1: -14.3 dB/)).toBeInTheDocument();
        expect(screen.getByText(/Track 2: -12.1 dB/)).toBeInTheDocument();
      });
    });

    it('should display formatted values for BPM dimensions', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/Track 1: 120 BPM/)).toBeInTheDocument();
        expect(screen.getByText(/Track 2: 140 BPM/)).toBeInTheDocument();
      });
    });

    it('should render progress bars for contributions', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        const progressBars = screen.getAllByRole('progressbar');
        expect(progressBars.length).toBeGreaterThan(0);
      });
    });
  });

  describe('All Dimensions Accordion', () => {
    it('should display accordion for all dimensions', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/view all 5 dimensions/i)).toBeInTheDocument();
      });
    });

    it('should expand accordion when clicked', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(async () => {
        const accordion = screen.getByText(/view all 5 dimensions/i);
        fireEvent.click(accordion);
      });

      // Should show all dimensions after expansion
      await waitFor(() => {
        expect(screen.getByText('Crest Db')).toBeInTheDocument();
        expect(screen.getByText('Stereo Width')).toBeInTheDocument();
      });
    });

    it('should sort dimensions by contribution', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(async () => {
        const accordion = screen.getByText(/view all 5 dimensions/i);
        fireEvent.click(accordion);
      });

      // Verify dimensions appear in descending contribution order
      const dimensionTexts = screen.getAllByText(/%$/);  // All contribution percentages end with %
      const contributions = dimensionTexts.map(el => parseFloat(el.textContent!));

      expect(contributions).toEqual([...contributions].sort((a, b) => b - a));
    });
  });

  describe('Props Handling', () => {
    it('should respect topN parameter', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} topN={3} />);

      await waitFor(() => {
        expect(similarityService.explainSimilarity).toHaveBeenCalledWith(1, 2, 3);
      });
    });

    it('should use default topN of 5', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(similarityService.explainSimilarity).toHaveBeenCalledWith(1, 2, 5);
      });
    });
  });

  describe('Auto-Update', () => {
    it('should reload when trackId1 changes', async () => {
      (similarityService.explainSimilarity as any)
        .mockResolvedValueOnce(mockExplanation)
        .mockResolvedValueOnce(mockExplanation);

      const { rerender } = render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(similarityService.explainSimilarity).toHaveBeenCalledWith(1, 2, 5);
      });

      rerender(<SimilarityVisualization trackId1={3} trackId2={2} />);

      await waitFor(() => {
        expect(similarityService.explainSimilarity).toHaveBeenCalledWith(3, 2, 5);
      });

      expect(similarityService.explainSimilarity).toHaveBeenCalledTimes(2);
    });

    it('should reload when trackId2 changes', async () => {
      (similarityService.explainSimilarity as any)
        .mockResolvedValueOnce(mockExplanation)
        .mockResolvedValueOnce(mockExplanation);

      const { rerender } = render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(similarityService.explainSimilarity).toHaveBeenCalledWith(1, 2, 5);
      });

      rerender(<SimilarityVisualization trackId1={1} trackId2={3} />);

      await waitFor(() => {
        expect(similarityService.explainSimilarity).toHaveBeenCalledWith(1, 3, 5);
      });

      expect(similarityService.explainSimilarity).toHaveBeenCalledTimes(2);
    });

    it('should reload when topN changes', async () => {
      (similarityService.explainSimilarity as any)
        .mockResolvedValueOnce(mockExplanation)
        .mockResolvedValueOnce(mockExplanation);

      const { rerender } = render(<SimilarityVisualization trackId1={1} trackId2={2} topN={5} />);

      await waitFor(() => {
        expect(similarityService.explainSimilarity).toHaveBeenCalledWith(1, 2, 5);
      });

      rerender(<SimilarityVisualization trackId1={1} trackId2={2} topN={3} />);

      await waitFor(() => {
        expect(similarityService.explainSimilarity).toHaveBeenCalledWith(1, 2, 3);
      });

      expect(similarityService.explainSimilarity).toHaveBeenCalledTimes(2);
    });

    it('should clear data when trackId1 becomes null', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      const { rerender } = render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('85%')).toBeInTheDocument();
      });

      rerender(<SimilarityVisualization trackId1={null} trackId2={2} />);

      expect(screen.queryByText('85%')).not.toBeInTheDocument();
      expect(screen.getByText(/select two tracks to compare/i)).toBeInTheDocument();
    });

    it('should clear data when trackId2 becomes null', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      const { rerender } = render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText('85%')).toBeInTheDocument();
      });

      rerender(<SimilarityVisualization trackId1={1} trackId2={null} />);

      expect(screen.queryByText('85%')).not.toBeInTheDocument();
      expect(screen.getByText(/select two tracks to compare/i)).toBeInTheDocument();
    });
  });

  describe('Value Formatting', () => {
    it('should format percentage dimensions correctly', async () => {
      const explanation: SimilarityExplanation = {
        ...mockExplanation,
        top_differences: [
          {
            dimension: 'bass_pct',
            contribution: 0.125,
            value1: 45.234,
            value2: 60.789,
            difference: 15.555
          }
        ]
      };

      (similarityService.explainSimilarity as any).mockResolvedValueOnce(explanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/45.2%/)).toBeInTheDocument();
        expect(screen.getByText(/60.8%/)).toBeInTheDocument();
      });
    });

    it('should format dB dimensions correctly', async () => {
      const explanation: SimilarityExplanation = {
        ...mockExplanation,
        top_differences: [
          {
            dimension: 'crest_db',
            contribution: 0.100,
            value1: 12.345,
            value2: 14.678,
            difference: 2.333
          }
        ]
      };

      (similarityService.explainSimilarity as any).mockResolvedValueOnce(explanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/12.3 dB/)).toBeInTheDocument();
        expect(screen.getByText(/14.7 dB/)).toBeInTheDocument();
      });
    });

    it('should format BPM dimensions correctly', async () => {
      const explanation: SimilarityExplanation = {
        ...mockExplanation,
        top_differences: [
          {
            dimension: 'tempo_bpm',
            contribution: 0.100,
            value1: 120.789,
            value2: 140.234,
            difference: 19.445
          }
        ]
      };

      (similarityService.explainSimilarity as any).mockResolvedValueOnce(explanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/121 BPM/)).toBeInTheDocument();
        expect(screen.getByText(/140 BPM/)).toBeInTheDocument();
      });
    });

    it('should format ratio/correlation dimensions correctly', async () => {
      const explanation: SimilarityExplanation = {
        ...mockExplanation,
        top_differences: [
          {
            dimension: 'phase_correlation',
            contribution: 0.100,
            value1: 0.85432,
            value2: 0.92156,
            difference: 0.06724
          }
        ]
      };

      (similarityService.explainSimilarity as any).mockResolvedValueOnce(explanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        expect(screen.getByText(/0.85/)).toBeInTheDocument();
        expect(screen.getByText(/0.92/)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA roles', async () => {
      (similarityService.explainSimilarity as any).mockResolvedValueOnce(mockExplanation);

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      await waitFor(() => {
        const progressBars = screen.getAllByRole('progressbar');
        expect(progressBars.length).toBeGreaterThan(0);
      });
    });

    it('should show loading indicator with aria-label', () => {
      (similarityService.explainSimilarity as any).mockImplementation(
        () => new Promise(() => {})
      );

      render(<SimilarityVisualization trackId1={1} trackId2={2} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });
});
