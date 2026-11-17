/**
 * Guards for the album-tracks, artist-detail and create-playlist responses (#6063).
 */

import { describe, it, expect } from 'vitest';
import {
  isAlbumTracksShape,
  isArtistDetailShape,
  isCreatePlaylistResponseShape,
} from '../responseGuards';

describe('isAlbumTracksShape', () => {
  it('accepts the album tracks envelope, with or without tracks', () => {
    expect(isAlbumTracksShape({ album_id: 1, total_tracks: 2, tracks: [{ id: 1 }, { id: 2 }] })).toBe(true);
    expect(isAlbumTracksShape({ album_id: 1, total_tracks: 0 })).toBe(true);
  });

  it('rejects a renamed or retyped field instead of letting it reach the transformer', () => {
    expect(isAlbumTracksShape({ tracks: 'nope' })).toBe(false);
    expect(isAlbumTracksShape({ tracks: [{ title: 'no id' }] })).toBe(false);
    expect(isAlbumTracksShape({ total_tracks: '3' })).toBe(false);
    expect(isAlbumTracksShape([])).toBe(false);
    expect(isAlbumTracksShape(null)).toBe(false);
  });
});

describe('isArtistDetailShape', () => {
  it('accepts an artist with an albums list', () => {
    expect(isArtistDetailShape({ id: 3, name: 'A', albums: [], total_albums: 0, total_tracks: 0 })).toBe(true);
  });

  it('rejects a missing name, id or albums list', () => {
    expect(isArtistDetailShape({ id: 3, albums: [] })).toBe(false);
    expect(isArtistDetailShape({ name: 'A', albums: [] })).toBe(false);
    expect(isArtistDetailShape({ id: 3, name: 'A' })).toBe(false);
  });
});

describe('isCreatePlaylistResponseShape', () => {
  it('accepts the {message, playlist} envelope', () => {
    expect(isCreatePlaylistResponseShape({ message: 'ok', playlist: { id: 1, name: 'P' } })).toBe(true);
  });

  it('rejects a bare playlist, which the backend never sends', () => {
    expect(isCreatePlaylistResponseShape({ id: 1, name: 'P' })).toBe(false);
    expect(isCreatePlaylistResponseShape({ playlist: { name: 'no id' } })).toBe(false);
  });
});
