/**
 * Type guards for values caught in a `catch` block.
 *
 * A `catch` binding is `unknown` — anything can be thrown, including strings,
 * plain objects and `undefined`. `(err as Error).name === 'AbortError'` asserts
 * a guarantee TypeScript never checked: it happens to work today because a
 * property read on a non-Error yields `undefined` rather than throwing, but it
 * licenses the next reader to reach for `err.stack` or `err.message` on a value
 * that may have neither (#4462).
 *
 * These helpers replace the assertions with checks that are true at runtime.
 */

/**
 * Is this a cancellation, rather than a real failure?
 *
 * `AbortController` aborts surface as a `DOMException` named `AbortError` in
 * browsers, but jsdom/happy-dom, polyfills and hand-rolled aborts throw plain
 * `Error`s with the same name, and some libraries throw bare objects. This
 * checks the name on any object, which is exactly what the `as Error` casts did
 * at runtime — the behaviour is unchanged, only the false type claim is gone.
 *
 * Returns `boolean` rather than narrowing to `e is DOMException` deliberately:
 * a narrowing predicate here would re-introduce the same unchecked promise for
 * every non-DOMException abort listed above.
 */
export function isAbortError(value: unknown): boolean {
  return (
    typeof value === 'object' &&
    value !== null &&
    'name' in value &&
    (value as { name?: unknown }).name === 'AbortError'
  );
}

/**
 * Coerce a caught value into a real `Error`.
 *
 * Use where code needs to *hold* an Error (store it, pass it to an `onError`
 * callback, re-throw it) rather than just inspect it. A non-Error is wrapped
 * with its string form as the message and the original kept on `cause`, so a
 * thrown string still produces a usable stack and nothing is lost.
 *
 * (`cause` is assigned rather than passed to the constructor: the project
 * targets ES2020, whose `Error` type has no options parameter.)
 */
export function toError(value: unknown): Error {
  if (value instanceof Error) {
    return value;
  }
  const error = new Error(typeof value === 'string' ? value : String(value));
  return Object.assign(error, { cause: value });
}
