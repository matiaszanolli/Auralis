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
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
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
function run(
  cases: Case[],
  baselineFailures: string[],
  extraFlags: string[] = [],
  checkPhantom = false
) {
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
      env: {
        ...process.env,
        TEST_BASELINE_PATH: baselinePath,
        // The #5344 cases use invented spec names; the phantom check has its own suite below.
        TEST_BASELINE_SKIP_PHANTOM: checkPhantom ? '0' : '1',
      },
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

describe('check-test-baseline.mjs phantom entries (#5811)', () => {
  // A spec that exists, with a title that appears verbatim in its source.
  const REAL_SPEC = 'src/__tests__/checkTestBaselineStrictStale.test.ts';
  const REAL_ENTRY = `${REAL_SPEC}::check-test-baseline.mjs --strict-stale (#5344) still fails on a brand-new unbaselined failure regardless of --strict-stale`;

  // A run that did not touch the baselined spec, so --strict-stale alone has nothing to say.
  const unrelatedRun = [{ file: 'src/other.test.ts', name: 'unrelated', failed: false }];

  it('flags an entry whose spec file no longer exists', () => {
    const result = run(unrelatedRun, ['src/deleted.test.ts::Suite does a thing'], [], true);

    expect(result.output).toContain('no longer exists');
    expect(result.output).toContain('src/deleted.test.ts::Suite does a thing');
  });

  it('flags an entry whose test title is gone from a spec that still exists', () => {
    // The shape of the two usePlayer entries #5354 orphaned: file present, describe deleted.
    // Joined at runtime: written out, the title would appear in this very file and be found.
    const goneTitle = ['Suite', 'a', 'title', 'nobody', 'wrote'].join(' ');
    const result = run(unrelatedRun, [`${REAL_SPEC}::${goneTitle}`], [], true);

    expect(result.output).toContain('no longer exists');
  });

  it('does not flag an entry whose spec and title are both present', () => {
    const result = run(unrelatedRun, [REAL_ENTRY], ['--strict-stale'], true);

    expect(result.output).not.toContain('no longer exists');
    expect(result.status).toBe(0);
  });

  it('fails --strict-stale on a phantom entry but not otherwise', () => {
    const phantomEntry = 'src/deleted.test.ts::Suite does a thing';

    expect(run(unrelatedRun, [phantomEntry], [], true).status).toBe(0);
    expect(run(unrelatedRun, [phantomEntry], ['--strict-stale'], true).status).toBe(1);
  });

  it('ships a baseline with no phantom entries', () => {
    const baseline = JSON.parse(
      readFileSync(join(FRONTEND_ROOT, 'test-baseline.json'), 'utf8')
    ) as { failures: string[] };
    const result = run(unrelatedRun, baseline.failures, ['--strict-stale'], true);

    expect(result.output).not.toContain('no longer exists');
  });
});
