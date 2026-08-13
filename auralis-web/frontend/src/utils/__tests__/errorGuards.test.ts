/**
 * Caught-value guards (#4462)
 *
 * `catch` bindings are `unknown`, so `(err as Error).name === 'AbortError'`
 * asserted a guarantee nothing had checked. These tests pin that the
 * replacements behave identically for the values actually thrown in this app —
 * DOMException aborts in the browser, plain Errors under happy-dom/jsdom — and
 * that they no longer promise an `Error` when a string or object was thrown.
 */

import { describe, it, expect } from 'vitest';
import { isAbortError, toError } from '../errorGuards';

describe('isAbortError', () => {
  it('recognises a real DOMException abort', () => {
    expect(isAbortError(new DOMException('The operation was aborted.', 'AbortError'))).toBe(true);
  });

  it('recognises the plain Error that jsdom/happy-dom and polyfills throw', () => {
    const err = new Error('Aborted');
    err.name = 'AbortError';
    expect(isAbortError(err)).toBe(true);
  });

  it('recognises an AbortController signal rejection', async () => {
    const controller = new AbortController();
    controller.abort();
    const rejected = await Promise.reject(controller.signal.reason).catch((e) => e);
    expect(isAbortError(rejected)).toBe(true);
  });

  it.each([
    ['a thrown string', 'AbortError'],
    ['a non-abort Error', new Error('boom')],
    ['null', null],
    ['undefined', undefined],
    ['a number', 42],
  ])('returns false for %s', (_label, value) => {
    expect(isAbortError(value)).toBe(false);
  });

  it('does not match a different DOMException', () => {
    expect(isAbortError(new DOMException('nope', 'NotFoundError'))).toBe(false);
  });
});

describe('toError', () => {
  it('passes a real Error through untouched', () => {
    const err = new Error('boom');
    expect(toError(err)).toBe(err);
  });

  it('preserves Error subclasses', () => {
    const err = new TypeError('bad type');
    expect(toError(err)).toBe(err);
    expect(toError(err)).toBeInstanceOf(TypeError);
  });

  it('wraps a thrown string, keeping the original on cause', () => {
    const wrapped = toError('something went wrong');
    expect(wrapped).toBeInstanceOf(Error);
    expect(wrapped.message).toBe('something went wrong');
    expect((wrapped as Error & { cause?: unknown }).cause).toBe('something went wrong');
  });

  it('wraps a thrown object so callers still get a usable Error', () => {
    const thrown = { code: 500 };
    const wrapped = toError(thrown);
    expect(wrapped).toBeInstanceOf(Error);
    expect(wrapped.message).toBe('[object Object]');
    expect((wrapped as Error & { cause?: unknown }).cause).toBe(thrown);
    expect(typeof wrapped.stack).toBe('string');
  });

  it.each([[undefined], [null], [0]])('never returns a non-Error (%s)', (value) => {
    expect(toError(value)).toBeInstanceOf(Error);
  });
});
