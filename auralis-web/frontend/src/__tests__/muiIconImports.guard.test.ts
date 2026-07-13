/// <reference types="node" />
/**
 * Guard: @mui/icons-material must be imported per-icon, never via the barrel (#4446)
 *
 * The barrel form (a braced import from the bare `@mui/icons-material` module)
 * re-exports ~2,000 icon modules and slows Vite dev cold-start / pre-bundling.
 * The per-icon path form `@mui/icons-material/Foo` (imported default) is
 * tree-shakable.
 *
 * This project has no ESLint setup, so this vitest guard is the enforced
 * regression check (it runs as part of `npm test`) in place of the
 * `no-restricted-imports` rule the issue proposed.
 */

import { describe, it, expect } from 'vitest';

// Barrel form only: `@mui/icons-material` immediately closed by a quote. The
// per-icon form `@mui/icons-material/Foo` (slash after) is explicitly allowed.
const BARREL_IMPORT = /from\s+['"]@mui\/icons-material['"]/;

const SELF = 'muiIconImports.guard.test.ts';

describe('@mui/icons-material imports (#4446)', () => {
  it('are all per-icon paths — no barrel imports remain', async () => {
    // Dynamic imports + process.cwd() (mirrors ErrorBoundary.test.tsx) so this
    // stays within the test tsconfig's `vitest/globals`-only types.
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
        } else if (/\.(ts|tsx)$/.test(entry) && entry !== SELF) {
          out.push(full);
        }
      }
      return out;
    };

    const offenders = collect(srcDir)
      .filter((file) => BARREL_IMPORT.test(fs.readFileSync(file, 'utf-8')))
      .map((file) => file.slice(srcDir.length + 1));

    expect(
      offenders,
      `Barrel import found. Use the per-icon path form instead, e.g.\n` +
        `  import Foo from '@mui/icons-material/Foo';\n` +
        `Offending files:\n${offenders.join('\n')}`
    ).toEqual([]);
  });
});
