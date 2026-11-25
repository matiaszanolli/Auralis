#!/usr/bin/env node
/**
 * Ratchet gate for frontend specs that assert (almost) nothing (#5682).
 *
 * The Python side has had scripts/check_weak_assertions.py since #5154; the frontend had no
 * equivalent and no linter, so weak specs regrew unchecked. Two defects, one baseline each:
 *
 *   zero    a test body with no assertion at all: no expect(...) / expect.<x>, no assert*(…),
 *           and no @ts-expect-error (a type-level spec's assertion is that tsc rejects the line),
 *           no call to a helper whose name starts with check, verify, expect or assert.
 *   weak    a test whose EVERY assertion is a presence check that passes for almost any value:
 *           toBeDefined, toBeTruthy, not.toBeNull, not.toBeUndefined. (A test that also asserts
 *           something specific is fine.)
 *   conditional  a test with an assertion inside an `if` that has no `else` (#6659): when the
 *           condition is false the behaviour the test is named for is never checked, and the
 *           other two rules still see an expect() and pass it. Query with getBy* and assert
 *           unconditionally instead.
 *
 * Offenders are listed as `path::test title`, never as a count, so strengthening one test and
 * weakening another cannot net out. The baseline may shrink, never grow.
 *
 * Usage:
 *   node scripts/check-weak-tests.mjs            verify
 *   node scripts/check-weak-tests.mjs --update   rewrite the baseline (only ever to shrink it)
 *   node scripts/check-weak-tests.mjs --list     print every current offender
 */

import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(ROOT, 'src');
const BASELINE_PATH = join(ROOT, 'weak-tests-baseline.json');

const WEAK_MATCHERS = new Set(['toBeDefined', 'toBeTruthy']);
const WEAK_NEGATED_MATCHERS = new Set(['toBeNull', 'toBeUndefined']);
const TEST_CALLEES = new Set(['it', 'test']);
const ASSERTING_HELPER = /^(assert|check|verify|expect)/i;

function* testFiles(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      if (name !== 'node_modules') yield* testFiles(path);
    } else if (/\.(test|spec)\.tsx?$/.test(name)) {
      yield path;
    }
  }
}

/** Vitest test calls, including table-driven and tagged-template .each forms. */
function asTestCall(node) {
  if (!ts.isCallExpression(node)) return null;
  let callee = node.expression;
  if (ts.isCallExpression(callee) || ts.isTaggedTemplateExpression(callee)) {
    const each = ts.isCallExpression(callee) ? callee.expression : callee.tag;
    if (!ts.isPropertyAccessExpression(each) || each.name.text !== 'each') return null;
    callee = each.expression;
  }
  while (ts.isPropertyAccessExpression(callee)) {
    if (!['skip', 'only', 'concurrent'].includes(callee.name.text)) return null;
    callee = callee.expression;
  }
  if (!ts.isIdentifier(callee) || !TEST_CALLEES.has(callee.text)) return null;
  const [title, body] = node.arguments;
  if (!title || !(ts.isStringLiteralLike(title) || ts.isTemplateExpression(title))) return null;
  if (!body || !(ts.isArrowFunction(body) || ts.isFunctionExpression(body))) return null;
  return { title: title.getText().slice(1, -1), body };
}

/** The matcher chain of an `expect(...)` call: [`not`, `toBeNull`] for expect(x).not.toBeNull(). */
function matcherChain(call) {
  const chain = [];
  let node = call.expression;
  while (ts.isPropertyAccessExpression(node)) {
    chain.unshift(node.name.text);
    node = node.expression;
  }
  return ts.isCallExpression(node) && node.expression.getText() === 'expect' ? chain : null;
}

function classify(body) {
  let assertions = 0;
  let strong = 0;
  let conditional = false;
  // Depth of `if` statements without an `else` enclosing the current node.
  let unguardedIfDepth = 0;
  const visit = (node) => {
    if (ts.isIfStatement(node) && !node.elseStatement) {
      visit(node.expression);
      unguardedIfDepth += 1;
      visit(node.thenStatement);
      unguardedIfDepth -= 1;
      return;
    }
    if (ts.isFunctionLike(node) && node !== body) {
      // A nested callback (waitFor, act, a helper) starts its own control flow.
      const saved = unguardedIfDepth;
      unguardedIfDepth = 0;
      ts.forEachChild(node, visit);
      unguardedIfDepth = saved;
      return;
    }
    if (ts.isCallExpression(node)) {
      const text = node.expression.getText();
      const chain = matcherChain(node);
      if (chain) {
        assertions += 1;
        if (unguardedIfDepth > 0) conditional = true;
        const negated = chain[0] === 'not';
        const matcher = chain[chain.length - 1];
        const weak = negated ? WEAK_NEGATED_MATCHERS.has(matcher) : WEAK_MATCHERS.has(matcher);
        if (!weak) strong += 1;
      } else if (text === 'expect') {
        // the inner expect(x) of a matcher chain; the chain itself is counted above
      } else if (/^expect\./.test(text) || ASSERTING_HELPER.test(text.split('.').pop() ?? '')) {
        assertions += 1;
        strong += 1;
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(body.body);
  if (assertions === 0 && body.getText().includes('@ts-expect-error')) return null;
  if (assertions === 0) return 'zero';
  if (strong === 0) return 'weak';
  return conditional ? 'conditional' : null;
}

export function scan(srcDir = SRC, base = ROOT) {
  const offenders = { zero: [], weak: [], conditional: [] };
  for (const file of testFiles(srcDir)) {
    const source = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
    const rel = relative(base, file);
    const visit = (node) => {
      const test = asTestCall(node);
      if (test) {
        const kind = classify(test.body);
        if (kind) offenders[kind].push(`${rel}::${test.title}`);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
  for (const key of Object.keys(offenders)) offenders[key].sort();
  return offenders;
}

function main() {
  const mode = process.argv[2];
  const current = scan();
  if (mode === '--list') {
    for (const [kind, ids] of Object.entries(current)) ids.forEach((id) => console.log(`${kind}\t${id}`));
    return 0;
  }
  if (mode === '--update') {
    writeFileSync(BASELINE_PATH, `${JSON.stringify(current, null, 2)}\n`);
    console.log(
      `Baseline updated: ${current.zero.length} zero-assertion, ${current.weak.length} weak-only, ` +
        `${current.conditional.length} conditional.`,
    );
    return 0;
  }
  const baseline = JSON.parse(readFileSync(BASELINE_PATH, 'utf8'));
  let failed = false;
  for (const kind of Object.keys(current)) {
    const allowed = new Set(baseline[kind] ?? []);
    const fresh = current[kind].filter((id) => !allowed.has(id));
    const fixed = (baseline[kind] ?? []).filter((id) => !current[kind].includes(id));
    if (fresh.length) {
      failed = true;
      const label = { zero: 'zero-assertion', weak: 'weak-only', conditional: 'conditional-assertion' }[kind];
      console.error(`✖ ${fresh.length} new ${label} test(s):`);
      fresh.forEach((id) => console.error(`    ${id}`));
    }
    if (fixed.length) {
      console.log(`+ ${fixed.length} ${kind} test(s) now fixed or removed; shrink the baseline: pnpm run test:weak:update`);
    }
  }
  if (failed) {
    console.error('A test must assert something specific. Strengthen it; the baseline may only shrink.');
    return 1;
  }
  console.log(
    `OK: no new weak tests (baseline: ${baseline.zero.length} zero, ${baseline.weak.length} weak-only, ` +
      `${(baseline.conditional ?? []).length} conditional).`,
  );
  return 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) process.exit(main());
