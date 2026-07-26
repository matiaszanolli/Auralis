/**
 * extractTrackFormat — #4586
 *
 * The queue utilities used to derive a track's format by parsing the extension
 * off `track.filepath`. No transport populates `filepath` (`Track.to_dict()`
 * omits it; `player_state.TrackInfo` marks it `Field(exclude=True)` per #3205),
 * so every queue-sourced track resolved to 'unknown' and both format
 * similarity and the format distribution silently collapsed.
 */

import { describe, it, expect } from 'vitest';
import { extractTrackFormat, UNKNOWN_FORMAT } from '../trackFormat';

describe('extractTrackFormat (#4586)', () => {
  it('prefers the explicit format the backend now sends', () => {
    expect(extractTrackFormat({ format: 'FLAC' })).toBe('flac');
  });

  it('resolves a format for a track that has no filepath at all', () => {
    // This is the real shape of a WS/REST-sourced queue track — the case that
    // used to always return 'unknown'.
    expect(extractTrackFormat({ format: 'mp3' })).toBe('mp3');
  });

  it('falls back to the filepath extension when no format is present', () => {
    expect(extractTrackFormat({ filepath: '/music/song.ogg' })).toBe('ogg');
  });

  it('prefers the explicit format over a conflicting filepath', () => {
    expect(extractTrackFormat({ format: 'flac', filepath: '/music/song.mp3' })).toBe('flac');
  });

  it('treats an empty or whitespace format as absent', () => {
    expect(extractTrackFormat({ format: '   ', filepath: '/m/a.wav' })).toBe('wav');
    expect(extractTrackFormat({ format: '' })).toBe(UNKNOWN_FORMAT);
  });

  it('handles null format (Python None over the wire)', () => {
    expect(extractTrackFormat({ format: null })).toBe(UNKNOWN_FORMAT);
    expect(extractTrackFormat({ format: null, filepath: '/m/a.aiff' })).toBe('aiff');
  });

  it('returns unknown for an unusable track', () => {
    expect(extractTrackFormat(undefined)).toBe(UNKNOWN_FORMAT);
    expect(extractTrackFormat({})).toBe(UNKNOWN_FORMAT);
    expect(extractTrackFormat({ filepath: '/music/no-extension' })).toBe(UNKNOWN_FORMAT);
  });
});
