/**
 * API response guards take `unknown`, and the remaining `any` uses are recorded (#4664)
 *
 * A type guard whose parameter is `any` accepts an already-wrong-shaped value
 * and narrows it with no compiler pushback — the exact opposite of what a guard
 * is for. Every guard on the API-response path takes `unknown`.
 *
 * #4693 retired `StandardizedAPIClient`, taking `isSuccessResponse` /
 * `isErrorResponse` and the envelope they described with it — nothing in
 * production called them, and the endpoints send their payload bare. The
 * signature check below therefore now covers the two guards that survived,
 * `isCacheStatsShape` / `isCacheHealthShape`, which is the same property on the
 * code that still exists.
 *
 * The second half of the issue is bookkeeping: a repo-wide `any` sweep keeps
 * being re-reported, so the accepted uses are recorded here as an allowlist that
 * a new occurrence has to be added to deliberately.
 */

import { describe, it, expect } from 'vitest';

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
  // 'a11y/focusManagement.ts' was here until #4392 deleted the dead
  // getAccessibleName() that was its only `any` use — the surviving
  // FocusManager class has none.
  'hooks/app/keyboardShortcutDefinitions.ts': 'handler signatures vary per shortcut',
  'design-system/primitives/Text.tsx': 'polymorphic `as` prop',
  'types/window.d.ts': 'ambient global augmentation',
  'utils/apiRequest.ts': 'the untyped fetch boundary itself',
  'hooks/api/useRestAPI.ts': 'generic REST hook over unconstrained shapes',
  'api/responseGuards.ts': 'documents that Response.json() is Promise<any>',
  'components/player/QueuePanel/QueuePanelExpanded.tsx': 'virtualizer ref interop',

  // The 'services/api/standardizedAPIClient.ts' entry that stood here named the
  // client's internal response cache map. #4693 retired the client, so the file
  // holds only types and guards and contains no `any` at all.
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

  it('the surviving cache guards declare `unknown`, not `any`', async () => {
    // Type-level, so runtime assertions cannot discriminate — this is the one
    // check that does, and it is why it exists. Repointed by #4693 from
    // isSuccessResponse/isErrorResponse, which were removed with the client,
    // onto the two guards that outlived it.
    const source = (await import('../standardizedAPIClient?raw')).default as string;

    for (const guard of ['isCacheStatsShape', 'isCacheHealthShape']) {
      const signature = source
        .split('\n')
        .find((line) => line.includes(`export function ${guard}`));

      expect(signature, `${guard} signature not found`).toBeDefined();
      expect(signature).toContain('v: unknown');
      expect(signature).not.toContain('v: any');
    }
  });

  it('the cache guards module is NOT on the allowlist', () => {
    // It was allowed only for the client's internal response-cache map, which
    // #4693 deleted. With the file down to types and guards there is nothing
    // to pre-approve, so a future `any` there must be caught by the sweep above
    // rather than found already permitted.
    expect(ALLOWED_ANY_FILES['services/api/standardizedAPIClient.ts']).toBeUndefined();
  });
});
