/**
 * Compile-time exhaustiveness for switches over a closed union (#6437).
 *
 * Put it in the `default:` of a switch that lists every member: once `value` is
 * narrowed to `never` the call type-checks, and adding a member to the union
 * makes `tsc` fail at this call instead of letting the new member fall into a
 * plausible-looking default (wrong label, colour or icon).
 *
 * At runtime it returns `fallback` rather than throwing: a value outside the
 * union can only arrive from outside the type system (a server frame, a stale
 * persisted setting), and a presentation helper must degrade, not crash a render.
 */
export function assertNever<T>(_value: never, fallback: T): T {
  return fallback;
}
