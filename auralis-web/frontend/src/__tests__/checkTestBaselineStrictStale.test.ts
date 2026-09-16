/**
 * Stale-baseline-entry detection for the frontend ratchet (#5344).
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * scripts/check-test-baseline.mjs computed "no longer fails" as
 * `baseline - current`, which conflates a baselined test that ran and
 * PASSED (genuinely stale -- it silently re-permits that exact failure
 * forever) with one simply absent from this run (a scoped invocation, an
 * --ignore'd file, a renamed/deleted test -- this report cannot prove those
 * pass). That conflation is why the check had no `--strict-stale` mode: a
 * scoped run would look like every out-of-scope entry had been fixed.
 *
 * Mirrors the backend's `check_pytest_baseline.py --strict-stale` fix
 * (#5091) with the same present/stale/not-run split, verified by spawning
 * the real script (a CLI with argv-driven process.exit() calls, not an
 * importable module) against synthetic vitest --reporter=json fixtures.
 *
 * :copyright: (C) 2026 Auralis Team
 * :license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const FRONTEND_ROOT = join(__dirname, '..', '..');
const SCRIPT_PATH = join(FRONTEND_ROOT, 'scripts', 'check-test-baseline.mjs');

interface Case {
  file: string;
  name: string;
  failed: boolean;
}

/** Build a vitest --reporter=json-shaped results file and a throwaway
 * baseline in an isolated tmp dir, then run the real script against them. */
function run(cases: Case[], baselineFailures: string[], extraFlags: string[] = []) {
  const dir = mkdtempSync(join(tmpdir(), 'baseline-5344-'));
  const byFile = new Map<string, Case[]>();
  for (const c of cases) {
    byFile.set(c.file, [...(byFile.get(c.file) ?? []), c]);
  }
  const testResults = [...byFile.entries()].map(([file, fileCases]) => ({
    name: join(FRONTEND_ROOT, file),
    status: fileCases.some((c) => c.failed) ? 'failed' : 'passed',
    assertionResults: fileCases.map((c) => ({
      fullName: c.name,
      status: c.failed ? 'failed' : 'passed',
    })),
  }));
  const numFailedTests = cases.filter((c) => c.failed).length;
  const resultsPath = join(dir, 'results.json');
  writeFileSync(
    resultsPath,
    JSON.stringify({
      numTotalTests: cases.length,
      numPassedTests: cases.length - numFailedTests,
      numFailedTests,
      testResults,
    })
  );

  const baselinePath = join(dir, 'test-baseline.json');
  writeFileSync(baselinePath, JSON.stringify({ failures: baselineFailures }));

  try {
    const output = execFileSync('node', [SCRIPT_PATH, resultsPath, ...extraFlags], {
      encoding: 'utf8',
      env: { ...process.env, TEST_BASELINE_PATH: baselinePath },
    });
    return { status: 0, output };
  } catch (err) {
    const e = err as { status: number | null; stdout?: string; stderr?: string };
    return { status: e.status ?? 1, output: `${e.stdout ?? ''}${e.stderr ?? ''}` };
  }
}

describe('check-test-baseline.mjs --strict-stale (#5344)', () => {
  it('reports a passing baselined test as stale without failing by default', () => {
    const result = run(
      [{ file: 'src/x.test.ts::m', name: 'was failing', failed: false }],
      ['src/x.test.ts::m::was failing']
    );

    expect(result.status).toBe(0);
    expect(result.output.toLowerCase()).toContain('stale');
    expect(result.output).toContain('src/x.test.ts::m::was failing');
  });

  it('fails when --strict-stale is set and a baselined test now passes', () => {
    const result = run(
      [{ file: 'src/x.test.ts::m', name: 'was failing', failed: false }],
      ['src/x.test.ts::m::was failing'],
      ['--strict-stale']
    );

    expect(result.status).toBe(1);
  });

  it('does not fail --strict-stale when the baselined test still fails', () => {
    const result = run(
      [{ file: 'src/x.test.ts::m', name: 'still failing', failed: true }],
      ['src/x.test.ts::m::still failing'],
      ['--strict-stale']
    );

    expect(result.status).toBe(0);
  });

  it('never fails --strict-stale on an entry absent from a scoped run', () => {
    // A scoped run must not look like every out-of-scope entry was fixed.
    const result = run(
      [{ file: 'src/y.test.ts::m', name: 'unrelated', failed: false }],
      ['src/other.test.ts::m::not in this run'],
      ['--strict-stale']
    );

    expect(result.status).toBe(0);
  });

  it('reports an absent entry separately from a stale one, and only the stale one is fatal', () => {
    const result = run(
      [{ file: 'src/x.test.ts::m', name: 'now passes', failed: false }],
      ['src/x.test.ts::m::now passes', 'src/gone.test.ts::m::deleted test'],
      ['--strict-stale']
    );

    expect(result.status).toBe(1);
    const staleSection = result.output.split('not in this report')[0];
    expect(staleSection).toContain('src/x.test.ts::m::now passes');
    expect(staleSection).not.toContain('src/gone.test.ts::m::deleted test');
  });

  it('still fails on a brand-new unbaselined failure regardless of --strict-stale', () => {
    const result = run(
      [{ file: 'src/x.test.ts::m', name: 'brand new failure', failed: true }],
      []
    );

    expect(result.status).toBe(1);
  });
});
