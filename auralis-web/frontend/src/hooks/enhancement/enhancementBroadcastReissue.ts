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
 * - suppression while a local command is in flight and for a window after it succeeds (local
 *   commands re-issue already). It starts before the request: the server broadcasts the change
 *   before it answers the POST, so the echo can arrive first (#6572);
 * - a once-per-message guard, because several `useEnhancementControl`
 *   instances subscribe and each holds its own state.
 */

/** How long after a local command succeeds its confirmation broadcast is still suppressed. */
export const LOCAL_COMMAND_SUPPRESS_MS = 2_000;

let _localCommandsInFlight = 0;
let _lastLocalCommandAt = 0;

/**
 * Start a local command, BEFORE its request: from now until it ends, and for
 * LOCAL_COMMAND_SUPPRESS_MS after a successful end, its broadcast is not external. Call the
 * returned `end` once with whether the request succeeded. A failed command opens no window, so a
 * genuine external change right after it is still honoured (#6572).
 */
export function beginLocalEnhancementCommand(): (succeeded: boolean) => void {
  _localCommandsInFlight += 1;
  let ended = false;
  return (succeeded) => {
    if (ended) return;
    ended = true;
    _localCommandsInFlight -= 1;
    if (succeeded) _lastLocalCommandAt = Date.now();
  };
}

/** True when no local command is in flight or recently succeeded (so this broadcast is external). */
export function isExternalChange(): boolean {
  return _localCommandsInFlight === 0 && Date.now() - _lastLocalCommandAt > LOCAL_COMMAND_SUPPRESS_MS;
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
