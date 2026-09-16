/**
 * httpError.ts field-validation-error parsing (#5351)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The backend's RequestValidationError handler (config/app.py) sends
 * `{"detail": "Validation error", "errors": [{"field", "message"}, ...]}` --
 * a shape readHttpErrorBody never parsed, so every 422 field-validation
 * error surfaced as the bare string "Validation error" regardless of which
 * field actually failed.
 *
 * :copyright: (C) 2026 Auralis Team
 * :license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { describe, expect, it } from 'vitest';
import { readHttpErrorBody } from '../httpError';

function jsonResponse(body: unknown, status = 422): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('readHttpErrorBody field-error parsing (#5351)', () => {
  it('renders a single field error, not the bare "Validation error" string', async () => {
    const response = jsonResponse({
      detail: 'Validation error',
      errors: [{ field: 'year', message: 'value is not a valid integer' }],
    });

    const result = await readHttpErrorBody(response);

    expect(result.parsed).toBe(true);
    expect(result.detail).toContain('year');
    expect(result.detail).toContain('value is not a valid integer');
    expect(result.detail).not.toBe('Validation error');
  });

  it('joins multiple field errors into one readable line', async () => {
    const response = jsonResponse({
      detail: 'Validation error',
      errors: [
        { field: 'year', message: 'value is not a valid integer' },
        { field: 'title', message: 'field required' },
      ],
    });

    const result = await readHttpErrorBody(response);

    expect(result.detail).toBe(
      'year: value is not a valid integer; title: field required'
    );
  });

  it('falls back to the message alone when a field is missing', async () => {
    const response = jsonResponse({
      detail: 'Validation error',
      errors: [{ message: 'top-level payload must be an object' }],
    });

    const result = await readHttpErrorBody(response);

    expect(result.detail).toBe('top-level payload must be an object');
  });

  it('falls back to `detail` when `errors` is present but empty', async () => {
    const response = jsonResponse({ detail: 'Validation error', errors: [] });

    const result = await readHttpErrorBody(response);

    expect(result.detail).toBe('Validation error');
  });

  it('falls back to `detail` when `errors` entries carry no usable message', async () => {
    const response = jsonResponse({
      detail: 'Validation error',
      errors: [{ field: 'year' }],
    });

    const result = await readHttpErrorBody(response);

    expect(result.detail).toBe('Validation error');
  });

  it('leaves FastAPI\'s own default `detail` array shape unchanged', async () => {
    // No top-level `errors` key at all in this shape -- `detail` IS the array.
    const response = jsonResponse({
      detail: [{ loc: ['body', 'year'], msg: 'field required', type: 'missing' }],
    });

    const result = await readHttpErrorBody(response);

    expect(result.detail).toBe('year: field required');
  });

  it('leaves a plain string `detail` (the common case) unchanged', async () => {
    const response = jsonResponse({ detail: 'Track 123 not found' }, 404);

    const result = await readHttpErrorBody(response);

    expect(result.detail).toBe('Track 123 not found');
  });

  it('still falls back gracefully on a non-JSON body', async () => {
    const response = new Response('not json', { status: 500 });

    const result = await readHttpErrorBody(response);

    expect(result.parsed).toBe(false);
    expect(result.detail).toBeUndefined();
  });
});
