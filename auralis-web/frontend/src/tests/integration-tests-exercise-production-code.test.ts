/**
 * Guard: an "integration test" must integrate with something (#5119).
 *
 * 14 files under `src/tests/integration/` and `src/tests/api-integration/`
 * imported zero production modules. Each defined a throwaway React component
 * inside the test file and asserted against that — so deleting the feature the
 * file named left every test in it green, while the docblocks and README
 * claimed integration coverage of search, filter, sort, metadata, artwork,
 * accessibility, API error handling, pagination, caching, bundle splitting and
 * memory cleanup.
 *
 * The identical defect was found and fixed once before, in
 * `integration/streaming-audio/streaming-mse.test.tsx` (#3935), and the fix was
 * never swept across the rest of the directory. This test is that sweep made
 * permanent: a new fixture-only suite fails here rather than sitting green for
 * another year.
 *
 * The rule: every spec in those trees must either import at least one
 * production module, or be explicitly skipped with a docstring saying why.
 * Skipping is the acknowledged-debt escape hatch (#5119/#3935), not a silent
 * pass — the skipped files are listed in `integration/README.md`.
 */

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

// `import.meta.url` is not a file: URL under the jsdom environment, so resolve
// from the vitest root instead (vitest.config.ts runs from the frontend dir).
const TESTS_ROOT = join(process.cwd(), 'src', 'tests');
const TREES = ['integration', 'api-integration'];

/** Import specifiers that are test infrastructure, not the app under test. */
const INFRASTRUCTURE = [
  'vitest',
  '@testing-library/',
  'msw',
  'react',
  'react-dom',
  '@/test/',
  'node:',
];

function collectSpecs(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...collectSpecs(full));
    } else if (/\.test\.tsx?$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

/** Every `from '...'` specifier that is not test infrastructure. */
function productionImports(source: string): string[] {
  const specifiers = [...source.matchAll(/from\s+['"]([^'"]+)['"]/g)].map((m) => m[1]);
  return specifiers.filter(
    (spec) => !INFRASTRUCTURE.some((prefix) => spec === prefix || spec.startsWith(prefix))
  );
}

/** A suite is exempt if every top-level describe is skipped. */
function isSkipped(source: string): boolean {
  const describes = [...source.matchAll(/^describe(\.\w+)?\(/gm)];
  return describes.length > 0 && describes.every((m) => m[1] === '.skip');
}

describe('integration specs exercise production code (#5119)', () => {
  const specs = TREES.flatMap((tree) => {
    try {
      return collectSpecs(join(TESTS_ROOT, tree));
    } catch {
      return []; // tree removed — nothing to guard
    }
  });

  it('finds the integration trees', () => {
    // Guards the guard: if the globbing silently matches nothing, every
    // assertion below passes vacuously — exactly the failure mode #5119 is about.
    expect(specs.length).toBeGreaterThan(10);
  });

  it.each(specs.map((s) => [relative(TESTS_ROOT, s), s]))(
    '%s imports production code or is explicitly skipped',
    (_label, path) => {
      const source = readFileSync(path, 'utf8');
      if (isSkipped(source)) return; // acknowledged debt — see integration/README.md

      expect(
        productionImports(source),
        `${relative(TESTS_ROOT, path)} imports no production module, so it can only ` +
          'test fixtures defined inside itself. Either import the component/hook it ' +
          'claims to cover, or mark it describe.skip with a docstring explaining why (#5119).'
      ).not.toHaveLength(0);
    }
  );
});
