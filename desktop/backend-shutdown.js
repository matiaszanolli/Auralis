'use strict';

/**
 * Stop the spawned backend: SIGTERM, then SIGKILL (child and its process group) once the grace
 * period passes without an exit. Resolves when the child has exited or been killed, so a quitting
 * app can wait for it instead of exiting first and leaving the SIGKILL timer to die with it (#5992).
 *
 * `killed` is not consulted: Node sets it as soon as a signal was *sent*, which is true right
 * after the SIGTERM, so a `!child.killed` guard on the escalation never lets it run. A child that
 * has already exited has a non-null exitCode or signalCode.
 *
 * @param {import('node:child_process').ChildProcess | null} child
 * @param {{ graceMs: number, killGroup?: (pid: number) => void, log?: (msg: string) => void }} options
 * @returns {Promise<void>}
 */
function terminateBackend(child, { graceMs, killGroup, log = () => {} }) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return Promise.resolve();
  return new Promise((resolve) => {
    let timer;
    child.once('exit', () => {
      clearTimeout(timer);
      resolve();
    });
    child.kill('SIGTERM');
    timer = setTimeout(() => {
      log('Backend still running after SIGTERM, sending SIGKILL...');
      child.kill('SIGKILL');
      if (killGroup && child.pid) {
        try {
          killGroup(child.pid);
          log('Killed process tree');
        } catch {
          // The group may already be gone.
        }
      }
      resolve();
    }, graceMs);
  });
}

module.exports = { terminateBackend };
