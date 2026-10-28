/**
 * Component-level @keyframes do not shadow the global ones (#6022)
 *
 * Emotion does not scope an `@keyframes` declared inside an object style: it emits a global,
 * unprefixed rule. DropZone, ProcessingToast and SettingsTabNav each declared their own `pulse`
 * (and DropZone a `fadeIn`), so the app had four same-named `pulse` keyframes with different
 * bodies, and the components that rely on the global name (TrackDisplay, ConnectionDetailsPanel)
 * got whichever definition was inserted last.
 *
 * Reading the sources is the check: the collision is a property of the declared names.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';

const SRC = join(__dirname, '..', '..');
const GLOBAL_NAMES = ['pulse', 'spin', 'fadeIn', 'slideUp'];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return entry === '__tests__' ? [] : sourceFiles(path);
    return /\.(ts|tsx)$/.test(entry) && !/\.test\./.test(entry) ? [path] : [];
  });
}

/** Names declared as `'@keyframes name'` object keys (a global rule once emitted). */
function objectKeyframeNames(file: string): string[] {
  return [...readFileSync(file, 'utf8').matchAll(/'@keyframes ([\w-]+)'\s*:/g)].map((m) => m[1]);
}

describe('object-style @keyframes names (#6022)', () => {
  const declared = sourceFiles(SRC).flatMap((file) =>
    objectKeyframeNames(file).map((name) => ({ file: file.slice(SRC.length + 1), name })),
  );

  it('finds the component keyframes it is meant to police', () => {
    expect(declared.map((d) => d.name)).toEqual(expect.arrayContaining(['dropZonePulse', 'processingToastPulse', 'scanDotPulse']));
  });

  it.each(GLOBAL_NAMES)('no component redeclares the global "%s"', (name) => {
    const clashes = declared.filter((d) => d.name === name);

    expect(clashes).toEqual([]);
  });

  it('every object-style keyframe name is declared once', () => {
    const counts = new Map<string, number>();
    declared.forEach(({ name }) => counts.set(name, (counts.get(name) ?? 0) + 1));

    expect([...counts].filter(([, count]) => count > 1)).toEqual([]);
  });
});
