import { describe, it, expect } from 'vitest';
import { pathBasename } from '../pathBasename';

describe('pathBasename', () => {
  it('takes the last segment of a POSIX path', () => {
    expect(pathBasename('/music/album/song.mp3')).toBe('song.mp3');
  });

  it('takes the last segment of a Windows path (#5913)', () => {
    expect(pathBasename('C:\\a\\b.mp3')).toBe('b.mp3');
  });

  it('handles mixed separators', () => {
    expect(pathBasename('C:\\Users\\me/Music\\song.mp3')).toBe('song.mp3');
  });

  it('ignores trailing separators', () => {
    expect(pathBasename('/music/album/')).toBe('album');
    expect(pathBasename('D:\\Music\\')).toBe('Music');
  });

  it('returns a bare name unchanged', () => {
    expect(pathBasename('song.mp3')).toBe('song.mp3');
  });

  it('returns the input when there is no segment', () => {
    expect(pathBasename('/')).toBe('/');
  });
});
