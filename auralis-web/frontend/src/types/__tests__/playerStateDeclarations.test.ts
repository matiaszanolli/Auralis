/**
 * One wire-facing player-state declaration, correctly documented (#3894).
 *
 * `types/api.ts`, `types/domain.ts` and `types/ws/player.ts` each declared a
 * player-state interface with overlapping field names. Nothing imported the
 * first two, so an IDE would autocomplete whichever it happened to find, and
 * the api.ts copy carried no volume-unit annotation at all.
 *
 * Two of the three also documented `volume` as "0.0 - 1.0". That matched
 * nothing: the backend clamps to 0-100 and defaults to 80, the Redux slice
 * clamps to 0-100, and `usePlaybackControl.setVolume` sends
 * `Math.round(v * 100)`. Only the type comment was wrong, so the defect is not
 * observable at runtime — the runtime scale is already covered by
 * `usePlaybackControl.test.ts`. A declaration-level defect needs a
 * declaration-level guard, which is what this is.
 *
 * #4398 went further and deleted api.ts's player-request types outright
 * (PlayerPlayRequest/PlayerSeekRequest/PlayerVolumeRequest/etc.) — zero real
 * importers, the same "nothing imported it" finding this file's own docstring
 * already made about api.ts's PlayerState. api.ts no longer declares any
 * player-state-adjacent type, so it dropped out of the "surviving
 * declarations state the 0-100 scale" check below; only domain.ts and
 * ws/player.ts remain to check.
 */

import { describe, it, expect } from 'vitest';
import apiTypes from '../api.ts?raw';
import domainTypes from '../domain.ts?raw';
import wsPlayerTypes from '../ws/player.ts?raw';

/** Strip block and line comments so prose about a type is not read as one. */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
}

/** Names of exported interfaces declared in a source file. */
function exportedInterfaces(src: string): string[] {
  return [...stripComments(src).matchAll(/export\s+interface\s+(\w+)/g)].map((m) => m[1]);
}

describe('player state type declarations (#3894)', () => {
  it('reads the sources it claims to guard', () => {
    // A failed raw import would make every assertion below vacuous.
    for (const src of [apiTypes, domainTypes, wsPlayerTypes]) {
      expect(src.length).toBeGreaterThan(0);
    }
  });

  it('api.ts no longer declares a duplicate PlayerState', () => {
    expect(exportedInterfaces(apiTypes)).not.toContain('PlayerState');
  });

  it('ws/player.ts remains the authoritative wire-facing shape', () => {
    expect(exportedInterfaces(wsPlayerTypes)).toContain('PlayerStateData');
    expect(exportedInterfaces(wsPlayerTypes)).toContain('RawPlayerStateData');
  });

  it('exactly one of the two type modules declares PlayerState', () => {
    const declaring = [
      ['api.ts', apiTypes],
      ['domain.ts', domainTypes],
    ].filter(([, src]) => exportedInterfaces(src as string).includes('PlayerState'));

    expect(declaring.map(([name]) => name)).toEqual(['domain.ts']);
  });

  it('no player type still documents volume as a 0.0-1.0 scale', () => {
    // The specific wrong annotation, in the two files that carried it.
    for (const [name, src] of [
      ['api.ts', apiTypes],
      ['domain.ts', domainTypes],
      ['ws/player.ts', wsPlayerTypes],
    ] as const) {
      expect(src, `${name} still documents volume as 0.0 - 1.0`).not.toMatch(
        /volume:\s*number;\s*\/\/\s*0\.0\s*-\s*1\.0/,
      );
    }
  });

  it('the surviving player-state declarations state the 0-100 scale', () => {
    expect(domainTypes).toMatch(/0-100/);
    expect(wsPlayerTypes).toMatch(/0-100/);
  });
});
