/**
 * crudService.custom()'s guard and result are tied to the endpoint name (#6052).
 *
 * `guards.custom` used to be `value is any`, so a guard for one shape on a call
 * typed `custom<Other>` compiled and the result type was never checked against
 * the runtime guard. These are compile-time assertions: `tsc` fails on a missing
 * or unused `@ts-expect-error`, and `expectTypeOf` is a no-op at runtime.
 */

import { describe, it, expectTypeOf } from 'vitest';
import { post } from '../apiRequest';
import type { RequestOptions } from '../apiRequestTypes';
import { createCrudService } from '../serviceFactory';

interface Archived { archivedCount: number }
interface Restored { restoredCount: number }

type ItemCustom = { archive: Archived; restore: Restored };

const isArchived = (value: unknown): value is Archived =>
  typeof value === 'object' && value !== null && 'archivedCount' in value;
const isRestored = (value: unknown): value is Restored =>
  typeof value === 'object' && value !== null && 'restoredCount' in value;

describe('crudService custom endpoints are typed per name (#6052)', () => {
  it('resolves each name to its declared shape', () => {
    const typeChecks = () => {
      const service = createCrudService<unknown, unknown, number, Record<string, unknown>, unknown, ItemCustom>({
        custom: { archive: '/api/items/archive', restore: '/api/items/restore' },
        guards: { custom: { archive: isArchived, restore: isRestored } },
      });

      expectTypeOf(service.custom('archive', 'post')).resolves.toEqualTypeOf<Archived>();
      expectTypeOf(service.custom('restore', 'post')).resolves.toEqualTypeOf<Restored>();
    };
    void typeChecks;
  });

  it('rejects a guard for the wrong shape and an unconfigured name', () => {
    const typeChecks = () => {
      createCrudService<unknown, unknown, number, Record<string, unknown>, unknown, ItemCustom>({
        custom: { archive: '/api/items/archive' },
        // @ts-expect-error -- a Restored guard cannot vouch for the archive response
        guards: { custom: { archive: isRestored } },
      });

      const service = createCrudService<unknown, unknown, number, Record<string, unknown>, unknown, ItemCustom>({});
      // @ts-expect-error -- 'purge' is not a custom endpoint of this service
      void service.custom('purge', 'post');
    };
    void typeChecks;
  });
});

describe('request bodies are Record<string, unknown>, not Record<string, any> (#6052)', () => {
  it('accepts plain object bodies and rejects non-objects', () => {
    const typeChecks = () => {
      const options: RequestOptions = { body: { name: 'x', nested: { a: 1 } } };
      void options;
      void post('/api/x', { name: 'x' });
      // @ts-expect-error -- a body is a JSON object, not a bare string
      void post('/api/x', 'raw');
    };
    void typeChecks;
  });
});
