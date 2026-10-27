/**
 * Context menu actions exist only for the callbacks supplied (#5614)
 *
 * The generators substituted `() => {}` for a missing callback, so the songs
 * list and the album/artist tables rendered Favourite / Go to Album / Go to
 * Artist / Track Info items that closed the menu and did nothing. An entry now
 * exists exactly when its handler does.
 */

import { describe, it, expect, vi } from 'vitest';
import {
  getTrackContextActions,
  getArtistContextActions,
  getPlaylistContextActions,
} from '../contextMenuActions';

const ids = (actions: { id: string }[]) => actions.map((a) => a.id);

describe('getTrackContextActions', () => {
  it('omits Favourite, Album, Artist, Similar and Info when their callbacks are absent', () => {
    const actions = getTrackContextActions(false, {
      onPlay: vi.fn(),
      onAddToQueue: vi.fn(),
    });

    expect(ids(actions)).toEqual(['play', 'queue']);
  });

  it('renders every entry, in order, when every callback is supplied', () => {
    const callbacks = {
      onPlay: vi.fn(),
      onAddToQueue: vi.fn(),
      onToggleLove: vi.fn(),
      onShowAlbum: vi.fn(),
      onShowArtist: vi.fn(),
      onFindSimilar: vi.fn(),
      onShowInfo: vi.fn(),
      onEditMetadata: vi.fn(),
      onDelete: vi.fn(),
    };

    const actions = getTrackContextActions(false, callbacks);

    expect(ids(actions)).toEqual([
      'play', 'queue', 'love', 'album', 'artist', 'similar', 'info', 'edit-metadata', 'delete',
    ]);
    actions.forEach((action) => action.onClick());
    Object.values(callbacks).forEach((callback) => expect(callback).toHaveBeenCalledTimes(1));
  });

  it('wires each entry to its own callback', () => {
    const onShowAlbum = vi.fn();
    const onFindSimilar = vi.fn();

    const actions = getTrackContextActions(false, { onShowAlbum, onFindSimilar });
    actions.find((a) => a.id === 'album')!.onClick();

    expect(onShowAlbum).toHaveBeenCalledTimes(1);
    expect(onFindSimilar).not.toHaveBeenCalled();
    expect(ids(actions)).toEqual(['album', 'similar']);
  });

  it('labels the favourite entry by the track state', () => {
    const labelOf = (isLoved: boolean) =>
      getTrackContextActions(isLoved, { onToggleLove: vi.fn() })[0].label;

    expect(labelOf(false)).toBe('Add to Favourites');
    expect(labelOf(true)).toBe('Remove from Favourites');
  });

  it('no longer lists Add to Playlist, which ContextMenu renders as its own section', () => {
    const actions = getTrackContextActions(false, { onPlay: vi.fn(), onAddToQueue: vi.fn() });

    expect(ids(actions)).not.toContain('playlist');
  });

  it('marks Remove from Library destructive and separates Edit Metadata above it', () => {
    const actions = getTrackContextActions(false, { onEditMetadata: vi.fn(), onDelete: vi.fn() });

    expect(actions.map((a) => [a.id, Boolean(a.divider), Boolean(a.destructive)])).toEqual([
      ['edit-metadata', true, false],
      ['delete', false, true],
    ]);
  });
});

describe('getArtistContextActions', () => {
  it('omits Show Albums and Artist Info without their callbacks', () => {
    expect(ids(getArtistContextActions({ onPlayAll: vi.fn(), onAddToQueue: vi.fn() }))).toEqual([
      'play-all', 'queue',
    ]);
  });

  it('returns nothing when no callback is supplied', () => {
    expect(getArtistContextActions({})).toEqual([]);
  });
});

describe('getPlaylistContextActions', () => {
  it('omits Edit and Delete without their callbacks', () => {
    expect(ids(getPlaylistContextActions({ onPlay: vi.fn() }))).toEqual(['play']);
  });

  it('renders all three with their callbacks', () => {
    const actions = getPlaylistContextActions({ onPlay: vi.fn(), onEdit: vi.fn(), onDelete: vi.fn() });

    expect(ids(actions)).toEqual(['play', 'edit', 'delete']);
    expect(actions[2].destructive).toBe(true);
  });
});
