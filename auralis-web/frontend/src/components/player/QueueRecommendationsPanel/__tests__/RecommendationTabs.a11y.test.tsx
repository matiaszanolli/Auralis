/**
 * Recommendation Tabs Keyboard Accessibility Tests (issue #3932)
 *
 * The "Add to queue" (+) button in all three recommendation tabs
 * (RecommendationTab, DiscoveryTab, NewArtistsTab) was only rendered when
 * the row was hovered, so it never appeared in the DOM for a keyboard user
 * to Tab to, and its only accessible name was `title=`. Each tab's
 * container row is now focusable, shows its Add button(s) on focus as well
 * as hover, and the button carries an aria-label.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RecommendationTab } from '../RecommendationTab';
import { DiscoveryTab } from '../DiscoveryTab';
import { NewArtistsTab } from '../NewArtistsTab';
import type { Track } from '@/types/domain';
import type { TrackRecommendation } from '@/utils/queue/queue_recommender';
import type { DiscoveryArtist } from '@/hooks/player/useQueueRecommendations';

const makeTrack = (id: number, title: string): Track => ({
  id,
  title,
  artist: 'Some Artist',
  album: 'Some Album',
  duration: 200,
  filepath: `/music/${id}.mp3`,
} as Track);

describe('RecommendationTab keyboard accessibility', () => {
  const recommendations: TrackRecommendation[] = [
    {
      track: makeTrack(1, 'Rec Track'),
      score: 0.8,
      reason: 'Similar artist',
      factors: { artist: 1, album: 0, format: 0, duration: 0 },
    },
  ];

  it('Add button is absent until the row is hovered or focused', () => {
    render(<RecommendationTab title="For You" recommendations={recommendations} onAddTrack={vi.fn()} />);
    expect(screen.queryByRole('button', { name: 'Add Rec Track to queue' })).not.toBeInTheDocument();
  });

  it('shows the Add button with an aria-label when the row receives keyboard focus', () => {
    render(<RecommendationTab title="For You" recommendations={recommendations} onAddTrack={vi.fn()} />);

    const row = screen.getByText('Rec Track').closest('[tabindex]') as HTMLElement;
    expect(row).toHaveAttribute('tabIndex', '0');
    fireEvent.focus(row);

    expect(screen.getByRole('button', { name: 'Add Rec Track to queue' })).toBeInTheDocument();
  });
});

describe('DiscoveryTab keyboard accessibility', () => {
  const tracks: Track[] = [makeTrack(2, 'Discovery Track')];

  it('shows the Add button with an aria-label when the row receives keyboard focus', () => {
    render(<DiscoveryTab tracks={tracks} onAddTrack={vi.fn()} />);

    expect(screen.queryByRole('button', { name: 'Add Discovery Track to queue' })).not.toBeInTheDocument();

    const row = screen.getByText('Discovery Track').closest('[tabindex]') as HTMLElement;
    fireEvent.focus(row);

    expect(screen.getByRole('button', { name: 'Add Discovery Track to queue' })).toBeInTheDocument();
  });
});

describe('NewArtistsTab keyboard accessibility', () => {
  const newArtists: DiscoveryArtist[] = [
    {
      artist: 'New Artist',
      trackCount: 1,
      tracks: [makeTrack(3, 'New Artist Track')],
    },
  ];

  it('shows the Add button with an aria-label when the card receives keyboard focus', () => {
    render(<NewArtistsTab newArtists={newArtists} onAddTrack={vi.fn()} />);

    expect(screen.queryByRole('button', { name: 'Add New Artist Track to queue' })).not.toBeInTheDocument();

    const card = screen.getByText('New Artist').closest('[tabindex]') as HTMLElement;
    fireEvent.focus(card);

    expect(screen.getByRole('button', { name: 'Add New Artist Track to queue' })).toBeInTheDocument();
  });
});
