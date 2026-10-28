/**
 * EmptyState and loading skeletons announce themselves (#5668)
 *
 * Empty states (no results, empty playlist, ...) appeared silently, and the
 * loading skeletons said nothing about being busy. EmptyState now carries
 * role="status" (implicitly polite live), the skeletons aria-busy.
 */

import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import { EmptyState, EmptyLibrary, NoSearchResults, EmptyQueue } from '../EmptyState';
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

describe('EmptyLibrary DropZone identity (#6033)', () => {
  // lazy() inside the component body made a new component type per render, so
  // every re-render unmounted DropZone and showed the Loading fallback again.
  it('keeps the DropZone mounted across re-renders instead of re-suspending', async () => {
    const onFolderDrop = () => {};
    const { rerender } = render(<EmptyLibrary onFolderDrop={onFolderDrop} scanning={false} />);
    await waitFor(() => expect(screen.queryByText('Loading...')).not.toBeInTheDocument());
    const dropZone = screen.getByRole('button', { name: /music folder/i });

    rerender(<EmptyLibrary onFolderDrop={onFolderDrop} scanning={true} />);

    expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /music folder/i })).toBe(dropZone);
  });
});

