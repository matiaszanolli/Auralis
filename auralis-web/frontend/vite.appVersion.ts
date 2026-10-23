import { readFileSync } from 'node:fs';

/**
 * The app version as a JSON string literal for Vite's `define` (#6253).
 *
 * `sync_version.py` keeps every package.json in lockstep with
 * `auralis/version.py`, so reading it here gives the renderer's
 * `window.__AURALIS_DEBUG__.version` the same single source of truth as the
 * backend instead of a hard-coded string that goes stale. Kept as a separate
 * module (like vite.manualChunks.ts) so a test can pin the wiring without
 * importing the whole config.
 */
export function appVersionDefineValue(packageJsonPath: string): string {
  const pkg = JSON.parse(readFileSync(packageJsonPath, 'utf8')) as { version: string };
  return JSON.stringify(pkg.version);
}
