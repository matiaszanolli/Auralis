/**
 * AddToPlaylistMenu — request cancellation on unmount/close (#4614)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `createCrudService` generated methods that called `get`/`post`/`put`/`del`
 * with no options object, so the five factory-built services could not abort
 * an in-flight request — the only HTTP layer excluded from the cancellation
 * discipline the rest of the codebase enforces.
 *
 * This component is the first opt-in consumer, and the reason the capability
 * is not dead code. It previously used a `cancelled` boolean, which suppresses
 * the state update but lets the request run to completion with no consumer.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import { AddToPlaylistMenu } from '../AddToPlaylistMenu';

vi.mock('@/services/playlistService', () => ({
  getPlaylists: vi.fn(),
}));

import { getPlaylists } from '@/services/playlistService';

const anchor = () => document.createElement('div');

const mockPlaylists = [
  { id: 1, name: 'Focus', track_count: 12 },
  { id: 2, name: 'Late Night', track_count: 4 },
];

beforeEach(() => {
  vi.mocked(getPlaylists).mockReset();
});

describe('AddToPlaylistMenu — cancellation (#4614)', () => {
  it('passes an AbortSignal to getPlaylists', async () => {
    vi.mocked(getPlaylists).mockResolvedValue({
      playlists: mockPlaylists,
      total: 2,
    } as never);

    render(
      <AddToPlaylistMenu anchorEl={anchor()} onClose={vi.fn()} onAddToPlaylist={vi.fn()} />
    );

    await waitFor(() => expect(getPlaylists).toHaveBeenCalled());

    const [, signal] = vi.mocked(getPlaylists).mock.calls[0];
    expect(signal).toBeInstanceOf(AbortSignal);
    expect((signal as AbortSignal).aborted).toBe(false);
  });

  it('aborts the in-flight request on unmount', async () => {
    let captured: AbortSignal | undefined;
    vi.mocked(getPlaylists).mockImplementation((async (
      _p: unknown,
      signal?: AbortSignal,
    ) => {
      captured = signal;
      // Never resolves — the request is still in flight at unmount.
      return new Promise(() => {});
    }) as never);

    const { unmount } = render(
      <AddToPlaylistMenu anchorEl={anchor()} onClose={vi.fn()} onAddToPlaylist={vi.fn()} />
    );

    await waitFor(() => expect(captured).toBeDefined());
    expect(captured!.aborted).toBe(false);

    unmount();

    expect(captured!.aborted).toBe(true);
  });

  it('aborts the superseded request when the menu is reopened', async () => {
    const signals: (AbortSignal | undefined)[] = [];
    vi.mocked(getPlaylists).mockImplementation((async (
      _p: unknown,
      signal?: AbortSignal,
    ) => {
      signals.push(signal);
      return new Promise(() => {});
    }) as never);

    const { rerender } = render(
      <AddToPlaylistMenu anchorEl={anchor()} onClose={vi.fn()} onAddToPlaylist={vi.fn()} />
    );
    await waitFor(() => expect(signals).toHaveLength(1));

    // Close, then reopen with a fresh anchor — the effect re-runs.
    rerender(
      <AddToPlaylistMenu anchorEl={null} onClose={vi.fn()} onAddToPlaylist={vi.fn()} />
    );
    rerender(
      <AddToPlaylistMenu anchorEl={anchor()} onClose={vi.fn()} onAddToPlaylist={vi.fn()} />
    );
    await waitFor(() => expect(signals).toHaveLength(2));

    expect(signals[0]!.aborted).toBe(true);
    expect(signals[1]!.aborted).toBe(false);
  });

  it('does not produce an unhandled rejection when the request rejects after unmount', async () => {
    // apiRequest re-throws AbortError; nothing downstream should surface it.
    const abortErr = Object.assign(new Error('The operation was aborted.'), {
      name: 'AbortError',
    });
    vi.mocked(getPlaylists).mockRejectedValue(abortErr);

    const onUnhandled = vi.fn();
    process.on('unhandledRejection', onUnhandled);
    try {
      const { unmount } = render(
        <AddToPlaylistMenu anchorEl={anchor()} onClose={vi.fn()} onAddToPlaylist={vi.fn()} />
      );
      await waitFor(() => expect(getPlaylists).toHaveBeenCalled());
      unmount();
      await new Promise((r) => setTimeout(r, 0));
      expect(onUnhandled).not.toHaveBeenCalled();
    } finally {
      process.off('unhandledRejection', onUnhandled);
    }
  });

  it('still renders playlists when the request completes normally', async () => {
    vi.mocked(getPlaylists).mockResolvedValue({
      playlists: mockPlaylists,
      total: 2,
    } as never);

    render(
      <AddToPlaylistMenu anchorEl={anchor()} onClose={vi.fn()} onAddToPlaylist={vi.fn()} />
    );

    expect(await screen.findByText('Focus (12)')).toBeInTheDocument();
    expect(screen.getByText('Late Night (4)')).toBeInTheDocument();
  });
});
