/// <reference types="node" />
/**
 * Guard: style-table lookups in the primitives are not asserted past the compiler (#6435)
 *
 * `variantStyles[variant as keyof typeof variantStyles]` compiles to the same type as the bare
 * lookup, but it silences the one error that matters: a variant added to the prop union without
 * a table entry becomes a silent `...undefined` spread (an unstyled control) instead of a
 * compile error. The tables are module-private, so the guard scans the source.
 */

import { describe, it, expect } from 'vitest';

describe('design-system primitives (#6435)', () => {
  it('index their style tables without an `as keyof typeof` assertion', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const dir = path.join(process.cwd(), 'src', 'design-system', 'primitives');

    const offenders = fs
      .readdirSync(dir)
      .filter((file) => /\.tsx?$/.test(file))
      .flatMap((file) =>
        fs
          .readFileSync(path.join(dir, file), 'utf8')
          .split('\n')
          .map((line, i) => ({ file, line: i + 1, text: line }))
          .filter(({ text }) => /\[\s*\w+ as keyof typeof \w+\s*\]/.test(text))
          .map(({ file: f, line }) => `${f}:${line}`),
      );

    expect(offenders).toEqual([]);
  });
});
