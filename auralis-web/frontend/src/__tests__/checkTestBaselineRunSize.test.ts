/**
 * Run-size and runner-exit sanity in the frontend baseline gate (#5679).
 *
 * The gate only required "more than zero tests", and CI ran vitest with `|| true`, so a run that
 * lost hundreds of specs (an include/exclude change, a worker killed on the heap limit that still
 * left a report) or exited non-zero without a failing assertion still said "No new test failures".
 * Verified by spawning the real script against synthetic vitest JSON, as checkTestBaselineStrictStale does.
 */

import { describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const FRONTEND_ROOT = join(__dirname, '..', '..');
const SCRIPT_PATH = join(FRONTEND_ROOT, 'scripts', 'check-test-baseline.mjs');

function run(opts: { total: number; failed?: string[]; baselineTotal?: number; baselineFailures?: string[]; exitCode?: string }) {
  const dir = mkdtempSync(join(tmpdir(), 'baseline-5679-'));
  const failed = opts.failed ?? [];
  const passedCount = opts.total - failed.length;
  const assertionResults = [
    ...failed.map((name) => ({ fullName: name, status: 'failed' })),
    ...Array.from({ length: passedCount }, (_, i) => ({ fullName: `passes ${i}`, status: 'passed' })),
  ];
  const resultsPath = join(dir, 'results.json');
  writeFileSync(
    resultsPath,
    JSON.stringify({
      numTotalTests: opts.total,
      numPassedTests: passedCount,
      numFailedTests: failed.length,
      testResults: [{ name: join(FRONTEND_ROOT, 'src/x.test.ts'), status: failed.length ? 'failed' : 'passed', assertionResults }],
    })
  );
  const baselinePath = join(dir, 'test-baseline.json');
  writeFileSync(
    baselinePath,
    JSON.stringify({
      generatedFrom: opts.baselineTotal === undefined ? undefined : { totalTests: opts.baselineTotal },
      failures: opts.baselineFailures ?? [],
    })
  );
  const env: NodeJS.ProcessEnv = { ...process.env, TEST_BASELINE_PATH: baselinePath, TEST_BASELINE_SKIP_PHANTOM: '1' };
  delete env.VITEST_EXIT_CODE;
  if (opts.exitCode !== undefined) env.VITEST_EXIT_CODE = opts.exitCode;
  try {
    return { status: 0, output: execFileSync('node', [SCRIPT_PATH, resultsPath], { encoding: 'utf8', env }) };
  } catch (err) {
    const e = err as { status: number | null; stdout?: string; stderr?: string };
    return { status: e.status ?? 1, output: `${e.stdout ?? ''}${e.stderr ?? ''}` };
  }
}

describe('check-test-baseline.mjs run-size floor (#5679)', () => {
  it('fails a run that collected well under what the baseline was generated from', () => {
    const result = run({ total: 500, baselineTotal: 1000 });

    expect(result.status).toBe(1);
    expect(result.output).toContain('collected 500 tests');
    expect(result.output).toContain('test:baseline:update');
  });

  it('accepts a modest shrink (a few specs deleted on purpose)', () => {
    expect(run({ total: 960, baselineTotal: 1000 }).status).toBe(0);
  });

  it('has no floor when the baseline predates the recorded size', () => {
    expect(run({ total: 5 }).status).toBe(0);
  });
});

describe('check-test-baseline.mjs runner exit code (#5679)', () => {
  it('fails when vitest exited non-zero but the report lists no failing test', () => {
    const result = run({ total: 10, exitCode: '1' });

    expect(result.status).toBe(1);
    expect(result.output).toContain('the runner itself failed');
  });

  it('accepts a non-zero exit that is explained by baselined failures', () => {
    const result = run({
      total: 10,
      failed: ['known bad'],
      baselineFailures: ['src/x.test.ts::known bad'],
      exitCode: '1',
    });

    expect(result.status).toBe(0);
  });

  it('accepts a clean run with no exit code supplied (local use)', () => {
    expect(run({ total: 10 }).status).toBe(0);
  });
});
