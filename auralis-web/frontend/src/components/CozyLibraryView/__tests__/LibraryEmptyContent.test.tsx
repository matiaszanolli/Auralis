/**
 * LibraryEmptyContent - a failed load is an error with a Retry, not "empty" (#6011).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@/test/test-utils';
import { LibraryEmptyContent } from '../LibraryEmptyContent';

const baseProps = {
  view: 'songs',
  searchQuery: '',
  scanning: false,
  onScanFolder: vi.fn(),
};

describe('LibraryEmptyContent', () => {
  it('shows the load error, not the empty-library prompt, when the fetch failed', () => {
    render(<LibraryEmptyContent {...baseProps} error="Network down" onRetry={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load your library");
    expect(screen.getByRole('alert')).toHaveTextContent('Network down');
    expect(screen.queryByText(/library is empty/i)).toBeNull();
  });

  it('names favorites when the favourites view failed to load', () => {
    render(<LibraryEmptyContent {...baseProps} view="favourites" error="boom" onRetry={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load your favorites");
    expect(screen.queryByText('No favorites yet')).toBeNull();
  });

  it('calls onRetry from the Try again button', () => {
    const onRetry = vi.fn();
    render(<LibraryEmptyContent {...baseProps} error="Network down" onRetry={onRetry} />);

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('omits the button when there is no retry handler', () => {
    render(<LibraryEmptyContent {...baseProps} error="Network down" />);

    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
  });

  it('still shows the favourites empty state when nothing failed', () => {
    render(<LibraryEmptyContent {...baseProps} view="favourites" error={null} />);

    expect(screen.getByText('No favorites yet')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
