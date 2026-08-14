/**
 * There is exactly one fixture source under test/mocks (#4698)
 *
 * `test/mocks/api.ts` exported a full parallel fixture set (`mockTrack`,
 * `mockTracks`, `mockAlbums`, `mockPlayerState`, `mockLibraryStats`, …) that no
 * test ever imported, while `mockData.ts` defines same-named fixtures that ARE
 * wired into the MSW handlers tests actually run against. The two had already
 * drifted — the dead module had `repeat: 'none'` where the live contract uses
 * `repeat_mode: 'off' | 'all' | 'one'` — and `src/test/README.md` pointed new
 * test authors at the dead one.
 *
 * These tests keep the trap from being rebuilt: no second fixture module, and
 * no documentation pointing at a module that does not exist.
 */

import { describe, expect, it } from 'vitest';

const mockModules = import.meta.glob('/src/test/mocks/*.ts', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

const docs = import.meta.glob('/src/test/README.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

describe('test/mocks has a single fixture source (#4698)', () => {
  it('the dead duplicate module is gone', () => {
    expect(Object.keys(mockModules)).not.toContain('/src/test/mocks/api.ts');
  });

  it('only one module exports each shared fixture name', () => {
    const FIXTURES = [
      'mockTracks',
      'mockAlbums',
      'mockPlayerState',
      'mockLibraryStats',
    ];

    for (const fixture of FIXTURES) {
      const owners = Object.entries(mockModules)
        .filter(([, src]) => new RegExp(`export const ${fixture}\\b`).test(src))
        .map(([path]) => path);

      expect(owners, `${fixture} must have exactly one owner`).toEqual([
        '/src/test/mocks/mockData.ts',
      ]);
    }
  });

  it('the live player-state fixture uses the real repeat_mode contract', () => {
    const src = mockModules['/src/test/mocks/mockData.ts'];

    expect(src).toContain('repeat_mode');
    // `repeat: 'none'` was the drifted field name on the dead module.
    expect(src).not.toMatch(/^\s*repeat:/m);
  });
});

describe('the testing README points only at live modules (#4698)', () => {
  it('every @/test/mocks import path in the README resolves', () => {
    const readme = docs['/src/test/README.md'];
    expect(readme, 'src/test/README.md not found').toBeDefined();

    const referenced = [
      ...readme.matchAll(/@\/test\/mocks\/([A-Za-z0-9_-]+)/g),
    ].map((m) => `/src/test/mocks/${m[1]}.ts`);

    expect(referenced.length).toBeGreaterThan(0);

    const missing = referenced.filter((p) => !(p in mockModules));
    expect(missing).toEqual([]);
  });

  it('the README does not resurrect the global fetch override', () => {
    // MSW is started for every test in setup.ts; assigning to global.fetch
    // silently bypasses it for the rest of the file and is never restored.
    const readme = docs['/src/test/README.md'];

    expect(readme).not.toContain('mockFetch');
    expect(readme).not.toContain('mockApiEndpoint');
  });
});
