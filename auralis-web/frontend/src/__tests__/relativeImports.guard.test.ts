/// <reference types="node" />
/**
 * Guard: no `../../` specifiers in imports or vi.mock paths (#6061)
 *
 * `@/` resolves identically in Vitest (alias in vitest.config.ts) and is the
 * project rule. Deep relative specifiers in `vi.mock`/`importOriginal` calls
 * crept back after #4466 converted the first batch: a moved file silently stops
 * matching its mock string. An ESLint `no-restricted-imports` pattern cannot see
 * the string argument of `vi.mock`, so this source-grep is the enforced check.
 *
 * Legitimate exceptions are specifiers that leave `src/` (the frontend root),
 * which `@/` cannot express; `import.meta.glob` scans are not matched at all.
 */

import { describe, it, expect } from 'vitest';

// `from '../../x'`, `import('../../x')`, `vi.mock('../../x'`, vi.importActual(...) etc.
const DEEP_RELATIVE =
  /(?:from\s+|import\s*\(\s*|\bvi\.(?:mock|doMock|importActual|importMock|unmock|doUnmock)\s*\(\s*)['"](?:\.\.\/){2,}/;

const ALLOWED_FILES = new Set([
  'viteChunking.test.ts', // reaches the frontend root
  'appVersionDefine.test.ts', // imports ../../vite.appVersion at the frontend root
  'relativeImports.guard.test.ts', // this file's own regex and docs
]);

describe('deep relative imports (#6061)', () => {
  it('use the @/ alias instead of ../../ specifiers', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const srcDir = path.join(process.cwd(), 'src');

    const collect = (dir: string): string[] => {
      const out: string[] = [];
      for (const entry of fs.readdirSync(dir)) {
        if (entry === 'node_modules') continue;
        const full = path.join(dir, entry);
        if (fs.statSync(full).isDirectory()) {
          out.push(...collect(full));
        } else if (/\.(ts|tsx)$/.test(entry) && !ALLOWED_FILES.has(entry)) {
          out.push(full);
        }
      }
      return out;
    };

    const offenders = collect(srcDir)
      .flatMap((file) =>
        fs
          .readFileSync(file, 'utf-8')
          .split('\n')
          .map((line, index) => ({ line, index }))
          .filter(({ line }) => DEEP_RELATIVE.test(line))
          .map(({ index }) => `${file.slice(srcDir.length + 1)}:${index + 1}`)
      );

    expect(
      offenders,
      `Use the '@/...' alias instead of '../../' specifiers.\nOffending lines:\n${offenders.join('\n')}`
    ).toEqual([]);
  });
});
