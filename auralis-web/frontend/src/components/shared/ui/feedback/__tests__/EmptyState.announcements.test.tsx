/**
 * EmptyState and loading skeletons announce themselves (#5668)
 *
 * Empty states (no results, empty playlist, ...) appeared silently, and the
 * loading skeletons said nothing about being busy. EmptyState now carries
 * role="status" (implicitly polite live), the skeletons aria-busy.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { EmptyState, NoSearchResults, EmptyQueue } from '../EmptyState';
import { TrackRowSkeleton } from '@/components/shared/ui/loaders/TrackRowSkeleton';
import { LibraryGridSkeleton } from '@/components/shared/ui/loaders/LibraryGridSkeleton';

describe('EmptyState status role (#5668)', () => {
  it('renders with role="status"', () => {
    render(<EmptyState title="No favorites yet" description="Heart some tracks" />);

    expect(screen.getByRole('status')).toHaveTextContent('No favorites yet');
  });

  it('announces the no-results variant, query included', () => {
    render(<NoSearchResults query="abba" />);

    expect(screen.getByRole('status')).toHaveTextContent('No results found');
    expect(screen.getByRole('status')).toHaveTextContent('abba');
  });

  it('keeps role="status" on the queue variant', () => {
    render(<EmptyQueue />);

    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});

describe('loading skeletons (#5668)', () => {
  it('marks the track row skeleton aria-busy', () => {
    const { container } = render(<TrackRowSkeleton />);

    expect(container.querySelector('[aria-busy="true"]')).toBeInTheDocument();
  });

  it('marks the library grid skeleton aria-busy', () => {
    const { container } = render(<LibraryGridSkeleton count={2} />);

    expect(container.querySelector('[aria-busy="true"]')).toBeInTheDocument();
  });
});
