/**
 * Automated accessibility assertions (#4637)
 *
 * There was no automated a11y testing anywhere in the frontend: no axe
 * dependency, nothing asserting roles, accessible names or focus order. Every
 * a11y regression could land silently — and several did. Six accessible-name
 * defects (#4448, #4449, #4450, #4473, #3996, #4180) were each found by manual
 * audit, and each is exactly what axe catches mechanically.
 *
 * ## Why axe-core directly instead of a matcher wrapper
 *
 * #4637 proposes `vitest-axe`. That package is at 0.1.0, was last published
 * 2025-01-22, and pulls chalk, redent, lodash-es, aria-query and
 * dom-accessibility-api along with axe-core — all to provide
 * `expect(...).toHaveNoViolations()`. `axe-core` is the actual engine, is
 * actively maintained, and the assertion is the ~20 lines below. One dependency
 * instead of a stale wrapper plus six transitive ones.
 *
 * ## What is and is NOT covered (read this before trusting a green run)
 *
 * jsdom has no layout engine, so a family of axe rules cannot work there and are
 * disabled explicitly below rather than left to report meaningless results:
 *
 * - `color-contrast` — needs composited pixels. jsdom resolves no cascade for
 *   translucent tokens over glass surfaces, so axe either skips it or guesses.
 *   Contrast is covered instead by explicit `contrastRatio()` assertions from
 *   real token values; see `src/test/contrast.ts` and the #4635 spec.
 * - `target-size` — needs box dimensions, which are all 0x0 in jsdom.
 * - Anything requiring a viewport or scroll position.
 *
 * So: this catches missing accessible names, role/attribute mismatches, invalid
 * ARIA, duplicate ids, and label/control associations. It does NOT catch
 * contrast, hit-target size, or real focus order. Do not read a clean axe run as
 * "this component is accessible".
 *
 * ## Two gaps axe does not cover, measured rather than assumed
 *
 * 1. **An interactive role on a non-focusable element.** `#4637`'s acceptance
 *    criteria require that introducing `role="button"` without `tabIndex`/
 *    `onKeyDown` fails a test. axe-core reports *nothing at all* for that —
 *    verified: no violation and no incomplete result. (The `focus-order-semantics`
 *    best-practice rule does not fire on it either.) So
 *    `findUnfocusableInteractiveRoles()` below implements that check directly,
 *    and it is asserted alongside axe rather than in place of it.
 * 2. **`incomplete` results are not violations.** axe returns rules it could not
 *    decide — e.g. `aria-valid-attr-value` for an `aria-labelledby` pointing at a
 *    missing element comes back *incomplete* in jsdom, not as a violation.
 *    Treating a clean `violations` array as a pass would silently ignore those,
 *    so they are surfaced too (opt-in via `strictIncomplete`).
 */

import { run as axeRun, type AxeResults, type RunOptions, type Result } from 'axe-core';

/**
 * Rules turned off because jsdom cannot evaluate them, not because we accept
 * violating them. Each has the alternative coverage noted above.
 */
export const JSDOM_UNSUPPORTED_RULES = [
  'color-contrast',
  'target-size',
] as const;

/**
 * Rendered components are fragments, not documents, so document-scoped rules
 * would fire on the test harness rather than the component under test.
 */
const FRAGMENT_SCOPED_RULES = [
  'html-has-lang',
  'landmark-one-main',
  'page-has-heading-one',
  'region',
  'document-title',
] as const;

const DEFAULT_DISABLED = [...JSDOM_UNSUPPORTED_RULES, ...FRAGMENT_SCOPED_RULES];

export interface A11yCheckOptions {
  /** Extra rule ids to disable for this call. Prefer fixing the violation. */
  disableRules?: string[];
  /** Restrict to specific axe tags, e.g. ['wcag2a', 'wcag2aa']. */
  tags?: string[];
  /** Also fail on axe `incomplete` results (rules axe could not decide). */
  strictIncomplete?: boolean;
  /** Skip the interactive-role focusability check. Rarely correct. */
  skipFocusableRoleCheck?: boolean;
}

/**
 * ARIA roles that imply the element is operable, so it must be focusable.
 * Kept to the roles this app actually applies to `div`/`span` wrappers.
 */
const INTERACTIVE_ROLES = [
  'button', 'link', 'checkbox', 'radio', 'switch', 'tab',
  'menuitem', 'option', 'slider', 'textbox', 'combobox',
] as const;

/** Elements that are focusable without an author-supplied tabindex. */
const NATIVELY_FOCUSABLE = 'a[href], button, input, select, textarea, summary, [contenteditable]';

/**
 * Elements carrying an interactive role that keyboard users cannot reach.
 *
 * axe does not catch this (see the module docstring), yet it is precisely the
 * defect class #4637 was filed over: a `role="button"` div that Tab skips.
 */
export function findUnfocusableInteractiveRoles(container: Element): string[] {
  const offenders: string[] = [];

  for (const role of INTERACTIVE_ROLES) {
    for (const el of Array.from(container.querySelectorAll(`[role="${role}"]`))) {
      const tabindex = el.getAttribute('tabindex');
      const focusable =
        (tabindex !== null && Number(tabindex) >= 0) || el.matches(NATIVELY_FOCUSABLE);
      if (!focusable) {
        offenders.push(
          `<${el.tagName.toLowerCase()} role="${role}"> is not keyboard focusable `
          + '(needs tabIndex={0}, or use a native control)'
        );
      }
    }
  }

  return offenders;
}

function formatViolations(violations: Result[]): string {
  return violations
    .map((v) => {
      const nodes = v.nodes
        .map((n) => `      ${n.html}\n      -> ${n.failureSummary ?? ''}`)
        .join('\n');
      return `  [${v.impact ?? 'unknown'}] ${v.id}: ${v.help}\n${nodes}\n      ${v.helpUrl}`;
    })
    .join('\n\n');
}

/**
 * Assert `container` has no axe violations under the enabled rule set.
 *
 * MUST be awaited — axe is async, so a forgotten `await` makes every violation
 * pass silently. Returns the raw results for callers that want to assert
 * something more specific.
 *
 * @example
 *   const { container } = render(<QueuePanel />);
 *   await expectNoA11yViolations(container);
 */
export async function expectNoA11yViolations(
  container: Element,
  options: A11yCheckOptions = {}
): Promise<AxeResults> {
  const disabled = [...DEFAULT_DISABLED, ...(options.disableRules ?? [])];

  const runOptions: RunOptions = {
    rules: Object.fromEntries(disabled.map((id) => [id, { enabled: false }])),
    ...(options.tags ? { runOnly: { type: 'tag', values: options.tags } } : {}),
  };

  const results = await axeRun(container, runOptions);

  const problems: string[] = [];

  if (results.violations.length > 0) {
    problems.push(
      `${results.violations.length} axe violation(s):\n${formatViolations(results.violations)}`
    );
  }

  if (!options.skipFocusableRoleCheck) {
    const unfocusable = findUnfocusableInteractiveRoles(container);
    if (unfocusable.length > 0) {
      problems.push(
        `${unfocusable.length} unreachable interactive role(s) — axe does not `
        + `report these:\n${unfocusable.map((m) => `  ${m}`).join('\n')}`
      );
    }
  }

  if (options.strictIncomplete && results.incomplete.length > 0) {
    problems.push(
      `${results.incomplete.length} undecided axe result(s):\n`
      + `${formatViolations(results.incomplete)}`
    );
  }

  if (problems.length > 0) {
    throw new Error(
      `Accessibility check failed.\n\n${problems.join('\n\n')}\n\n`
      + 'Note: contrast and hit-target size are NOT checked here (jsdom has no '
      + 'layout) — see src/test/a11y.ts.'
    );
  }

  return results;
}

/**
 * Collect violations without throwing.
 *
 * For the meta-tests that assert the checker actually catches a seeded defect,
 * and for triaging a component with known pre-existing violations.
 */
export async function getA11yViolations(
  container: Element,
  options: A11yCheckOptions = {}
): Promise<Result[]> {
  const disabled = [...DEFAULT_DISABLED, ...(options.disableRules ?? [])];
  const results = await axeRun(container, {
    rules: Object.fromEntries(disabled.map((id) => [id, { enabled: false }])),
  });
  return results.violations;
}

/**
 * axe results the engine could not decide, for the same triage purpose.
 *
 * jsdom pushes several rules here rather than into `violations` — notably
 * `aria-valid-attr-value` for a reference to a missing element.
 */
export async function getA11yIncomplete(
  container: Element,
  options: A11yCheckOptions = {}
): Promise<Result[]> {
  const disabled = [...DEFAULT_DISABLED, ...(options.disableRules ?? [])];
  const results = await axeRun(container, {
    rules: Object.fromEntries(disabled.map((id) => [id, { enabled: false }])),
  });
  return results.incomplete;
}
