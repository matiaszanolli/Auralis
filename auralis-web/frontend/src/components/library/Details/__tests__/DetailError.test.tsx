/**
 * Shared error / not-found state of the album and artist detail views (#6034).
 *
 * The artist view's error branch rendered only the EmptyState; the album view had
 * a Back button. A user landing on a stale artist link had nothing but the
 * sidebar to leave by.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { DetailError } from '../DetailError';

describe('DetailError', () => {
  it('renders the title and description', () => {
    render(<DetailError title="Artist not found" description="Gone." backLabel="Back to Artists" />);

    expect(screen.getByText('Artist not found')).toBeInTheDocument();
    expect(screen.getByText('Gone.')).toBeInTheDocument();
  });

  it('offers a Back button that calls onBack', async () => {
    const onBack = vi.fn();
    render(<DetailError title="Error Loading Artist" onBack={onBack} backLabel="Back to Artists" />);

    await userEvent.click(screen.getByRole('button', { name: /back to artists/i }));

    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('renders no button when there is nowhere to go back to', () => {
    render(<DetailError title="Artist not found" backLabel="Back to Artists" />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('can announce itself as an alert', () => {
    render(<DetailError title="Error Loading Artist" backLabel="Back" alert />);

    expect(screen.getByRole('alert')).toHaveTextContent('Error Loading Artist');
  });
});
