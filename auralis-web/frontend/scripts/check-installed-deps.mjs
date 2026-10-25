#!/usr/bin/env node
/**
 * Installed-vs-lockfile dependency guard (#6008).
 *
 * The jsdom ^30.1.0 bump (a800893e) made CI and the lockfile move while one
 * local node_modules stayed on jsdom 27.3.0. A baseline regenerated from
 * that stale install under-reported the failures CI actually hits (jsdom 30
 * FocusTrap restore-focus TypeErrors), and the frontend ratchet has been red
 * on every run since. This script refuses baseline regeneration whenever the
 * installed jsdom/vitest — the two packages that shape the whole test
 * environment — differ from what pnpm-lock.yaml resolves, so a baseline can
 * only ever be written from the dependency set CI runs.
 *
 * Usage (wired into `pnpm run test:baseline:update`):
 *   node scripts/check-installed-deps.mjs
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

/** The version pnpm-lock.yaml resolves for a top-level devDependency. */
function lockfileVersion(pkg) {
  // Overridable so a test can exercise the drift path against a throwaway
  // tampered lockfile, mirroring check-test-baseline.mjs's
  // TEST_BASELINE_PATH (#5344).
  const lockPath = process.env.TEST_LOCKFILE_PATH
    ? resolve(process.env.TEST_LOCKFILE_PATH)
    : resolve(FRONTEND_ROOT, 'pnpm-lock.yaml');
  const lock = readFileSync(lockPath, 'utf8');
  // Only the importers section: the packages section carries every transitive
  // copy, and the baseline environment is defined by the direct deps.
  const importers = lock.slice(0, lock.indexOf('\npackages:'));
  const match = importers.match(
    new RegExp(`\\n\\s+${pkg}:\\n\\s+specifier: [^\\n]+\\n\\s+version: ([^\\s]+)`)
  );
  if (!match) return null;
  // Peer-dependency suffixes ("4.1.11(@types/node@24.12.4)(...)") are part of
  // the resolution id, not the version.
  return match[1].split('(')[0];
}

/** The version actually installed in node_modules. */
function installedVersion(pkg) {
  try {
    const pkgJson = JSON.parse(
      readFileSync(resolve(FRONTEND_ROOT, 'node_modules', pkg, 'package.json'), 'utf8')
    );
    return pkgJson.version;
  } catch {
    return null;
  }
}

// jsdom defines the DOM the suite runs in; vitest defines how it runs. Those
// two moved the baseline last time (#6008); anything else moving is caught
// by `pnpm install --frozen-lockfile` in CI itself.
const GUARDED = ['jsdom', 'vitest'];

let drifted = false;
for (const pkg of GUARDED) {
  const installed = installedVersion(pkg);
  const locked = lockfileVersion(pkg);
  if (installed === null) {
    console.error(`✖ ${pkg} is not installed — run \`pnpm install\` first.`);
    drifted = true;
  } else if (locked === null) {
    console.error(`✖ ${pkg} not found in pnpm-lock.yaml importers — is it still a direct dependency?`);
    drifted = true;
  } else if (installed !== locked) {
    console.error(`✖ installed ${pkg}@${installed} does not match lockfile ${locked}.`);
    console.error(`  A baseline written from this node_modules reproduces the #6008 drift.`);
    console.error(`  Run \`pnpm install\` and regenerate from the CI dependency set.`);
    drifted = true;
  } else {
    console.log(`✓ ${pkg}@${installed} matches the lockfile`);
  }
}

process.exit(drifted ? 1 : 0);
