/**
 * Guard: every `vi.mock('<path>')` names a module that exists (#5678).
 *
 * Nine mocks in four specs pointed at modules that were moved or deleted, so
 * they silently did nothing and the real components rendered instead of the
 * stubs the assertions looked for (19 baselined LibraryEmptyState failures).
 * Vitest does not complain about a mock for a path that resolves to nothing,
 * so this walks every spec, resolves each `@/` or relative `vi.mock` string the
 * way the app's aliases do, and fails on a miss.
 *
 * Bare package names (`vitest`, `react`, ...) are not checked here.
 */

import { describe, it, expect } from 'vitest';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';

const SRC = join(process.cwd(), 'src');
const EXTENSIONS = ['', '.ts', '.tsx', '.js', '.jsx', '.json', '.css'];

function collectSpecs(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry !== 'node_modules') out.push(...collectSpecs(full));
    } else if (/\.test\.tsx?$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

function resolvesToAFile(base: string): boolean {
  return (
    EXTENSIONS.some((ext) => existsSync(base + ext) && statSync(base + ext).isFile()) ||
    ['index.ts', 'index.tsx', 'index.js'].some((index) => existsSync(join(base, index)))
  );
}

/** `vi.mock`/`vi.doMock` string targets that are aliases or relative paths. */
function localMockTargets(source: string): string[] {
  const targets = [...source.matchAll(/^[ \t]*vi\.(?:do)?[mM]ock\(\s*['"]([^'"]+)['"]/gm)].map((m) => m[1]);
  return targets.filter((target) => target.startsWith('@/') || target.startsWith('.'));
}

function resolveTarget(spec: string, target: string): string {
  return target.startsWith('@/') ? join(SRC, target.slice(2)) : resolve(dirname(spec), target);
}

describe('vi.mock targets exist (#5678)', () => {
  it('has no mock for a module that does not exist', () => {
    const missing: string[] = [];
    for (const spec of collectSpecs(SRC)) {
      for (const target of localMockTargets(readFileSync(spec, 'utf8'))) {
        if (!resolvesToAFile(resolveTarget(spec, target))) {
          missing.push(`${relative(SRC, spec)}: vi.mock('${target}')`);
        }
      }
    }

    expect(missing, `mocks of modules that do not exist (a no-op mock):\n${missing.join('\n')}`).toEqual([]);
  });

  it('would catch a missing target (the resolver is not vacuous)', () => {
    expect(resolvesToAFile(join(SRC, 'components/shared/ui/feedback'))).toBe(true);
    expect(resolvesToAFile(join(SRC, 'components/shared/EmptyState'))).toBe(false);
    expect(localMockTargets("vi.mock('@/hooks/usePlayerCommands', () => ({}))")).toEqual(['@/hooks/usePlayerCommands']);
  });
});
