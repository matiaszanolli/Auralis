#!/usr/bin/env node
/**
 * Ratchet gate for the vitest suite (#4640).
 *
 * Nothing ever ran vitest in CI, which is how a large pre-existing failure
 * baseline accumulated unnoticed. Demanding a green suite on day one would
 * mean the gate is disabled on day one, so instead this compares the current
 * failures against a checked-in baseline and fails only on *new* ones. The
 * baseline can shrink but never grow.
 *
 * Usage:
 *   node scripts/check-test-baseline.mjs <results.json>               # verify
 *   node scripts/check-test-baseline.mjs <results.json> --update       # rewrite baseline
 *   node scripts/check-test-baseline.mjs <results.json> --strict-stale # also fail on stale entries
 *
 * Stale entries are the other half of the ratchet (#5344, mirroring the
 * backend's #5091 fix in check_pytest_baseline.py): a baselined test that
 * starts passing but keeps its entry silently re-permits that exact failure,
 * so the test can regress and CI stays green. Staleness is always *reported*;
 * --strict-stale makes it *fail*, and counts only tests actually present in
 * the report (ran, whether it passed or failed), so a scoped run that never
 * touched a baselined spec cannot trip it.
 *
 * Exit codes: 0 = no new failures, 1 = new failures (or unusable input),
 * 1 = stale entries when --strict-stale is set.
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, '..');
// Overridable so a test can exercise this script (a CLI with argv-driven
// process.exit() calls, not an importable module) against a throwaway
// baseline via a subprocess, instead of monkeypatching the real
// test-baseline.json (#5344).
const BASELINE_PATH = process.env.TEST_BASELINE_PATH
  ? resolve(process.env.TEST_BASELINE_PATH)
  : resolve(FRONTEND_ROOT, 'test-baseline.json');

const [, , resultsArg, ...flags] = process.argv;
const UPDATE = flags.includes('--update');
const STRICT_STALE = flags.includes('--strict-stale');

if (!resultsArg) {
  console.error('usage: check-test-baseline.mjs <vitest-json-results> [--update] [--strict-stale]');
  process.exit(1);
}

/** Read the vitest `--reporter=json` output, failing loudly if it is unusable. */
function readResults(path) {
  let raw;
  try {
    raw = readFileSync(resolve(process.cwd(), path), 'utf8');
  } catch (err) {
    console.error(`✖ Could not read vitest results at ${path}: ${err.message}`);
    console.error('  The suite most likely crashed before writing a report.');
    process.exit(1);
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    console.error(`✖ vitest results at ${path} are not valid JSON: ${err.message}`);
    process.exit(1);
  }
  if (!Array.isArray(parsed.testResults)) {
    console.error(`✖ vitest results at ${path} have no testResults array.`);
    process.exit(1);
  }
  // A run that collected nothing is a broken runner, not a green suite.
  if (!parsed.numTotalTests) {
    console.error('✖ vitest reported 0 total tests — treating as a failed run.');
    process.exit(1);
  }
  return parsed;
}

/**
 * Identify a failure by `<repo-relative file>::<full test name>`.
 *
 * Names rather than a bare count: a count-only baseline goes green when one
 * test starts failing and another is deleted. Paths are made relative so the
 * baseline is identical on a developer machine and on a CI runner.
 */
function collectFailures(results) {
  const failures = new Set();
  for (const suite of results.testResults) {
    const file = relative(FRONTEND_ROOT, suite.name).split('\\').join('/');
    const assertions = suite.assertionResults ?? [];
    for (const assertion of assertions) {
      if (assertion.status === 'failed') {
        failures.add(`${file}::${assertion.fullName}`);
      }
    }
    // A suite that fails to collect (import error, syntax error) reports no
    // assertions at all — record the file itself so it cannot slip through.
    if (suite.status === 'failed' && !assertions.some((a) => a.status === 'failed')) {
      failures.add(`${file}::<suite failed to run>`);
    }
  }
  return failures;
}

/**
 * Every test id that actually ran in this report, regardless of outcome
 * (#5344) — used to tell "baselined and now passing" (stale) apart from
 * "baselined but absent from this report" (a scoped run, an --ignore'd file,
 * or a renamed/deleted test), which a bare `!current.has(id)` check cannot
 * distinguish. Mirrors collectFailures' suite-failed-to-collect handling so
 * a synthetic `<suite failed to run>` entry is only ever "present" when that
 * suite actually reported something this run.
 */
function collectPresent(results) {
  const present = new Set();
  for (const suite of results.testResults) {
    const file = relative(FRONTEND_ROOT, suite.name).split('\\').join('/');
    const assertions = suite.assertionResults ?? [];
    for (const assertion of assertions) {
      present.add(`${file}::${assertion.fullName}`);
    }
    if (suite.status === 'failed' && !assertions.some((a) => a.status === 'failed')) {
      present.add(`${file}::<suite failed to run>`);
    }
  }
  return present;
}

const results = readResults(resultsArg);
const current = collectFailures(results);

if (UPDATE) {
  const payload = {
    _comment:
      'Known-failing vitest specs (#4640). CI fails on any failure NOT listed here. ' +
      'Regenerate with: pnpm run test:baseline:update',
    generatedFrom: {
      totalTests: results.numTotalTests,
      failedTests: results.numFailedTests,
    },
    failures: [...current].sort(),
  };
  writeFileSync(BASELINE_PATH, `${JSON.stringify(payload, null, 2)}\n`);
  console.log(`✔ Baseline updated: ${current.size} known failures.`);
  process.exit(0);
}

let baseline;
try {
  baseline = new Set(JSON.parse(readFileSync(BASELINE_PATH, 'utf8')).failures ?? []);
} catch (err) {
  console.error(`✖ Could not read baseline at ${BASELINE_PATH}: ${err.message}`);
  process.exit(1);
}

const present = collectPresent(results);
const added = [...current].filter((id) => !baseline.has(id)).sort();
// Split what the old code lumped together as "no longer fails" (#5344,
// mirroring #5091's backend fix): a baselined test that ran and PASSED is
// stale and must be removed; one absent from this report was simply not run
// (scoped run, --ignore'd, renamed/deleted) and this report cannot prove it
// passes.
const stale = [...baseline].filter((id) => present.has(id) && !current.has(id)).sort();
const notRun = [...baseline].filter((id) => !present.has(id)).sort();

console.log(
  `Vitest: ${results.numPassedTests} passed, ${results.numFailedTests} failed ` +
  `(baseline allows ${baseline.size}).`
);

if (stale.length) {
  console.log(`\n✔ ${stale.length} baseline failure(s) ran and PASSED — stale:`);
  for (const id of stale.slice(0, 20)) console.log(`    ${id}`);
  if (stale.length > 20) console.log(`    ... and ${stale.length - 20} more`);
  console.log(
    '  Each one silently re-permits that exact failure: the test can regress and CI stays green.\n' +
    '  Remove them, or run `pnpm run test:baseline:update` and commit to tighten the gate.'
  );
}

if (notRun.length) {
  console.log(
    `\nℹ ${notRun.length} baseline entry(ies) were not in this report ` +
    '(scoped run, --ignore\'d file, or renamed/deleted test).'
  );
  for (const id of notRun.slice(0, 20)) console.log(`    ${id}`);
  if (notRun.length > 20) console.log(`    ... and ${notRun.length - 20} more`);
  console.log('  Not treated as stale — this report cannot prove they pass.');
}

if (added.length) {
  console.error(`\n✖ ${added.length} NEW test failure(s) not in the baseline:\n`);
  for (const id of added) console.error(`    ${id}`);
  console.error(
    '\nFix them, or — only if the failure is genuinely pre-existing and was ' +
    'merely unmasked — run `pnpm run test:baseline:update` and explain why in the PR.'
  );
  process.exit(1);
}

if (stale.length && STRICT_STALE) {
  console.error(
    `\n✖ --strict-stale: ${stale.length} baselined test(s) now pass. ` +
    'The ratchet may shrink, never grow — tighten it.'
  );
  process.exit(1);
}

console.log('\n✔ No new test failures.');
