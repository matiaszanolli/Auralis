/**
 * Shared timing constants (#5800).
 *
 * `staleTime: 5 * 60 * 1000` was typed in App.tsx and three fingerprint-hook
 * sites, each with its own comment, so retuning one left the others. They now
 * read QUERY_STALE_TIME_MS. This fails if a numeric staleTime literal returns
 * to shipped code (`staleTime: 0` in the test harness is not shipped).
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { QUERY_STALE_TIME_MS, SEARCH_DEBOUNCE_MS } from '../timing';

const SRC = join(__dirname, '..', '..');

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      return name === '__tests__' || name === 'test' ? [] : sources(path);
    }
    return /\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

describe('shared timing constants', () => {
  it('are positive millisecond values', () => {
    expect(QUERY_STALE_TIME_MS).toBeGreaterThan(1000);
    expect(SEARCH_DEBOUNCE_MS).toBeGreaterThan(0);
    expect(SEARCH_DEBOUNCE_MS).toBeLessThan(2000);
  });

  it('keep React Query staleTime out of shipped code as a literal', () => {
    const offenders = sources(SRC).filter((file) =>
      /staleTime:\s*[\d(]/.test(readFileSync(file, 'utf8'))
    );

    expect(offenders.map((f) => relative(SRC, f))).toEqual([]);
  });

  it('keep gcTime and the similarity cache TTL out of shipped code as literals (#6064)', () => {
    const offenders = sources(SRC).filter((file) => {
      const text = readFileSync(file, 'utf8');
      return /gcTime:\s*[\d(]/.test(text) || /CACHE_TTL_MS\s*=\s*[\d(]/.test(text);
    });

    expect(offenders.map((f) => relative(SRC, f))).toEqual([]);
  });
});
