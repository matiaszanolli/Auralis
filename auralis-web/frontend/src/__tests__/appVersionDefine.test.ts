/**
 * The renderer's product-version source of truth (#6253).
 *
 * `window.__AURALIS_DEBUG__.version` used to be a hard-coded string that
 * drifted three releases behind `auralis/version.py`. vite.config.mts now
 * injects it via `define: { __APP_VERSION__ }`, reading the version from
 * package.json — which `sync_version.py` keeps in lockstep with
 * auralis/version.py. These tests pin that chain: the helper JSON-quotes the
 * version from the package.json it is pointed at, and both ends of the wiring
 * (the define in vite.config.mts, the read in index.tsx) are asserted against
 * the config's own source, since the main tsconfig cannot import a .mts
 * config module from src/.
 */

import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { appVersionDefineValue } from '../../vite.appVersion';

describe('__APP_VERSION__ define (#6253)', () => {
  it('JSON-quotes the version from the package.json it reads', () => {
    const dir = mkdtempSync(join(tmpdir(), 'appversion-'));
    const pkgPath = join(dir, 'package.json');
    writeFileSync(pkgPath, JSON.stringify({ version: '9.9.9-test' }));

    expect(appVersionDefineValue(pkgPath)).toBe('"9.9.9-test"');
  });

  it('injects the helper under the exact key index.tsx reads', () => {
    // vitest runs with cwd = the frontend root, where both files live.
    const configSource = readFileSync('vite.config.mts', 'utf8');
    const entrySource = readFileSync('src/index.tsx', 'utf8');

    expect(configSource).toContain("import { appVersionDefineValue } from './vite.appVersion'");
    expect(configSource).toMatch(/__APP_VERSION__:\s*appVersionDefineValue\(/);
    expect(entrySource).toContain('version: __APP_VERSION__');
    expect(entrySource).not.toMatch(/version:\s*'\d+\.\d+/);
  });
});
