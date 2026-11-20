'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { terminateBackend } = require('./backend-shutdown');

function fakeChild({ exitsOn = null } = {}) {
  const child = new EventEmitter();
  child.pid = 4242;
  child.exitCode = null;
  child.signalCode = null;
  child.killed = false;
  child.signals = [];
  child.kill = (signal) => {
    child.killed = true; // Node sets this as soon as a signal is sent, not when the process exits
    child.signals.push(signal);
    if (signal === exitsOn || signal === 'SIGKILL') {
      setImmediate(() => child.emit('exit', null, signal));
    }
    return true;
  };
  return child;
}

test('a backend that ignores SIGTERM is SIGKILLed after the grace period, even though killed is already true (#5992)', async () => {
  const child = fakeChild();
  const groups = [];
  await terminateBackend(child, { graceMs: 20, killGroup: (pid) => groups.push(pid) });
  assert.deepEqual(child.signals, ['SIGTERM', 'SIGKILL']);
  assert.deepEqual(groups, [4242]);
});

test('a backend that exits on SIGTERM is not SIGKILLed and the promise settles on its exit', async () => {
  const child = fakeChild({ exitsOn: 'SIGTERM' });
  await terminateBackend(child, { graceMs: 5000 });
  assert.deepEqual(child.signals, ['SIGTERM']);
});

test('an already-exited or missing backend is a no-op', async () => {
  const gone = fakeChild();
  gone.exitCode = 0;
  await terminateBackend(gone, { graceMs: 20 });
  await terminateBackend(null, { graceMs: 20 });
  assert.deepEqual(gone.signals, []);
});

test('a failing process-group kill does not stop the escalation', async () => {
  const child = fakeChild();
  await terminateBackend(child, { graceMs: 10, killGroup: () => { throw new Error('ESRCH'); } });
  assert.deepEqual(child.signals, ['SIGTERM', 'SIGKILL']);
});
