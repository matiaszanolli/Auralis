/**
 * MasteringRecommendation rendering (#4166)
 *
 * MasteringRecommendationData was defined 4x with divergent shapes; domain.ts
 * marked weighted_profiles REQUIRED, which threw when iterating it for
 * non-hybrid profiles. The canonical type (types/ws/enhancement) makes it
 * optional. These tests pin that a non-hybrid recommendation (no
 * weighted_profiles) renders without crashing, and a hybrid one shows the blend.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MasteringRecommendation from '../MasteringRecommendation';
import type { MasteringRecommendationData } from '@/types/websocket';

const baseRec: MasteringRecommendationData = {
  track_id: 1,
  primary_profile_id: 'warm',
  primary_profile_name: 'Warm Master',
  confidence_score: 0.9,
  predicted_loudness_change: 1.0,
  predicted_crest_change: -0.2,
  predicted_centroid_change: 0.1,
  reasoning: 'Best tonal match',
  is_hybrid: false,
};

describe('MasteringRecommendation (#4166)', () => {
  it('renders a non-hybrid recommendation without weighted_profiles (no crash)', () => {
    expect(() =>
      render(<MasteringRecommendation recommendation={baseRec} />)
    ).not.toThrow();

    expect(screen.getByText('Warm Master')).toBeInTheDocument();
    expect(screen.getByText('90% match')).toBeInTheDocument();
  });

  it('renders the hybrid blend when weighted_profiles are present', () => {
    const hybrid: MasteringRecommendationData = {
      ...baseRec,
      is_hybrid: true,
      weighted_profiles: [
        { profile_id: 'warm', profile_name: 'Warm', weight: 0.6 },
        { profile_id: 'bright', profile_name: 'Bright', weight: 0.4 },
      ],
    };

    render(<MasteringRecommendation recommendation={hybrid} />);

    expect(screen.getByText('Warm Master')).toBeInTheDocument();
    // The second blended profile name ('Bright') is unique to the blend section.
    expect(screen.getByText('Bright')).toBeInTheDocument();
  });

  it('returns nothing when recommendation is null', () => {
    const { container } = render(<MasteringRecommendation recommendation={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
