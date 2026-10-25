/**
 * Enhancement broadcast re-issue coordination (#5864)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `enhancement_settings_changed` arrives from TWO origins: this client's own
 * REST commands (toggle/preset/intensity — which already re-issue the active
 * stream themselves, #3759/#3763) and external writers such as the Settings
 * dialog's save, which never re-issues. The stream loop re-reads `enabled`
 * per chunk and stops early when it flips false, so an external change with
 * no re-issue strands playback on a dead stream.
 *
 * Two guards make the broadcast-driven re-issue fire exactly once, and never
 * on top of a local command's own re-issue:
 *
 * - a suppression window after every local command (they re-issue already);
 * - a once-per-message guard, because several `useEnhancementControl`
 *   instances subscribe and each holds its own state.
 */

/** How long after a local command its confirmation broadcast is suppressed. */
export const LOCAL_COMMAND_SUPPRESS_MS = 2_000;

let _lastLocalCommandAt = 0;

/** Call before a local command re-issues — its broadcast must not re-issue too. */
export function markLocalEnhancementCommand(): void {
  _lastLocalCommandAt = Date.now();
}

/** True when no local command happened recently (so this broadcast is external). */
export function isExternalChange(): boolean {
  return Date.now() - _lastLocalCommandAt > LOCAL_COMMAND_SUPPRESS_MS;
}

const _handledMessages = new WeakSet<object>();

/**
 * Run `fn` only for the first subscriber to process this message object.
 * Every mounted subscriber receives the same broadcast instance, so the
 * WeakSet gives exactly-once semantics without a coordinator.
 */
export function oncePerMessage<T extends object>(message: T, fn: () => void): void {
  if (_handledMessages.has(message)) return;
  _handledMessages.add(message);
  fn();
}
