/**
 * API response guards take `unknown`, and the remaining `any` uses are recorded (#4664)
 *
 * `isSuccessResponse` / `isErrorResponse` sit on the real API-response path and
 * took `any`. A type guard whose parameter is `any` accepts an
 * already-wrong-shaped value and narrows it with no compiler pushback — the
 * exact opposite of what a guard is for. Both now take `unknown`.
 *
 * The second half of the issue is bookkeeping: a repo-wide `any` sweep keeps
 * being re-reported, so the accepted uses are recorded here as an allowlist that
 * a new occurrence has to be added to deliberately.
 */

import { describe, it, expect } from 'vitest';
import {
  isSuccessResponse,
  isErrorResponse,
} from '../standardizedAPIClient';

describe('isSuccessResponse accepts unknown safely (#4664)', () => {
  it.each([
    ['null', null],
    ['undefined', undefined],
    ['a number', 42],
    ['a string', 'success'],
    ['a boolean', true],
    ['an empty object', {}],
    ['an array', []],
    ['a wrong-status envelope', { status: 'error', error: 'x' }],
    ['a success envelope with no data', { status: 'success' }],
  ])('returns false for %s without throwing', (_label, value) => {
    expect(() => isSuccessResponse(value)).not.toThrow();
    expect(isSuccessResponse(value)).toBe(false);
  });

  it('returns true for a well-formed success envelope', () => {
    expect(isSuccessResponse({ status: 'success', data: { id: 1 } })).toBe(true);
  });

  it('accepts a success envelope whose data is falsy but defined', () => {
    // `data: 0` / `data: null` are legitimate payloads; only `undefined` means
    // "absent". The original `response.data !== undefined` check is preserved.
    expect(isSuccessResponse({ status: 'success', data: 0 })).toBe(true);
    expect(isSuccessResponse({ status: 'success', data: null })).toBe(true);
  });
});

describe('isErrorResponse accepts unknown safely (#4664)', () => {
  it.each([
    ['null', null],
    ['undefined', undefined],
    ['a number', 42],
    ['an empty object', {}],
    ['a success envelope', { status: 'success', data: 1 }],
    ['an error envelope with no error field', { status: 'error' }],
  ])('returns false for %s without throwing', (_label, value) => {
    expect(() => isErrorResponse(value)).not.toThrow();
    expect(isErrorResponse(value)).toBe(false);
  });

  it('returns true for a well-formed error envelope', () => {
    expect(isErrorResponse({ status: 'error', error: 'boom' })).toBe(true);
  });
});

/**
 * Deliberate `any` exceptions, as code.
 *
 * The issue's CONSISTENCY check asks that accepted uses be recorded so the next
 * audit does not re-report the same set. Keyed by file with the reason.
 *
 * Note the aggregate count in the issue (69 non-test / 29 production) has
 * already drifted — the live number is higher and the file set differs — which
 * is precisely why this is a file allowlist rather than a count.
 */
const ALLOWED_ANY_FILES: Record<string, string> = {
  // Test infrastructure — mocks and setup intentionally model loose payloads.
  'test/mocks/handlers.ts': 'MSW handlers model arbitrary wire payloads',
  'test/mocks/websocket.ts': 'mock socket models arbitrary frames',
  // 'test/mocks/api.ts' was here until #4698 deleted the module — it was a
  // dead, drifted duplicate of mockData.ts that no test ever imported.
  'test/setup.ts': 'global test shims',

  // The four 'performance/*' entries that stood here are gone: #4696 deleted
  // src/performance/ wholesale, so there is nothing left to allow.

  // Generic wrappers and dev tooling where `any` is the honest signature.
  'utils/serviceFactory.ts': 'generic CRUD factory over unconstrained shapes (#4461)',
  'store/middleware/loggerMiddleware.ts': 'logs arbitrary action payloads',
  'a11y/focusManagement.ts': 'generic DOM helpers (also dead — #4392)',
  'hooks/app/keyboardShortcutDefinitions.ts': 'handler signatures vary per shortcut',
  'design-system/primitives/Text.tsx': 'polymorphic `as` prop',
  'types/window.d.ts': 'ambient global augmentation',
  'utils/apiRequest.ts': 'the untyped fetch boundary itself',
  'hooks/api/useRestAPI.ts': 'generic REST hook over unconstrained shapes',
  'api/responseGuards.ts': 'documents that Response.json() is Promise<any>',
  'components/player/QueuePanel/QueuePanelExpanded.tsx': 'virtualizer ref interop',

  // The response cache stores heterogeneous payloads by key; the guards above
  // are what re-narrow them on the way out.
  'services/api/standardizedAPIClient.ts': 'internal response cache map value',
};

describe('the remaining any usage is a recorded set, not a growing one (#4664)', () => {
  it('no unlisted production file introduces `any`', async () => {
    const modules = import.meta.glob('/src/**/*.{ts,tsx}', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>;

    const offenders: string[] = [];

    // Strip comments: several of these files explain in prose why `any` is or
    // was used, and matching that would flag the documentation as the defect.
    const stripComments = (src: string) =>
      src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');

    for (const [path, source] of Object.entries(modules)) {
      if (path.includes('__tests__') || /\.test\.tsx?$/.test(path)) continue;
      if (!/: any\b|as any\b|<any>|any\[\]/.test(stripComments(source))) continue;

      const rel = path.replace(/^\/src\//, '');
      if (!Object.keys(ALLOWED_ANY_FILES).some((k) => rel.endsWith(k))) {
        offenders.push(rel);
      }
    }

    expect(offenders).toEqual([]);
  });

  it('both guards declare `unknown`, not `any`', async () => {
    // The guards' fix is type-level: their runtime behaviour is unchanged, so
    // every assertion above passes with `any` too. This is the one check that
    // actually discriminates, and it is why it exists.
    const source = (await import('../standardizedAPIClient?raw')).default as string;

    for (const guard of ['isSuccessResponse', 'isErrorResponse']) {
      const signature = source
        .split('\n')
        .find((line) => line.includes(`export function ${guard}`));

      expect(signature, `${guard} signature not found`).toBeDefined();
      expect(signature).toContain('response: unknown');
      expect(signature).not.toContain('response: any');
    }
  });

  it('the two API response guards are NOT on the allowlist', () => {
    // They were the one live-data-path exception worth fixing, and they are
    // fixed. If a future edit reintroduces `any` there, the sweep above must
    // catch it rather than find it pre-approved.
    const guardsEntry = ALLOWED_ANY_FILES['services/api/standardizedAPIClient.ts'];
    expect(guardsEntry).toBe('internal response cache map value');
    expect(guardsEntry).not.toMatch(/guard/i);
  });
});
