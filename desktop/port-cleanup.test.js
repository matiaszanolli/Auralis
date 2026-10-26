'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const {
  isAuralisBackendCommand,
  listenCommand,
  parseListenerPids,
  commandLineCommand,
  findListeners,
  stopProcess,
} = require('./port-cleanup');

// #6157: cleanupPort() SIGKILLed every PID `lsof -ti:PORT` printed, and that
// lists clients (a browser tab, the Vite proxy, curl) as well as the listener.

test('unix discovery only asks for LISTEN-state sockets', () => {
  assert.equal(listenCommand('linux', 8765), 'lsof -nP -iTCP:8765 -sTCP:LISTEN -t');
});

test('unix parse keeps PIDs and ignores noise', () => {
  assert.deepEqual(parseListenerPids('4242\n\n4242\nwarning: x\n', 'linux', 8765), ['4242']);
});

const NETSTAT = [
  '  Proto  Local Address          Foreign Address        State           PID',
  '  TCP    127.0.0.1:8765         0.0.0.0:0              LISTENING       111',
  '  TCP    127.0.0.1:8765         127.0.0.1:53000        ESTABLISHED     222',
  '  TCP    127.0.0.1:53000        127.0.0.1:8765         ESTABLISHED     333',
  '  TCP    127.0.0.1:87650        0.0.0.0:0              LISTENING       444',
  '  TCP    0.0.0.0:18765          0.0.0.0:0              LISTENING       555',
].join('\r\n');

test('windows parse selects only the LISTENING row whose LOCAL address is the port', () => {
  assert.deepEqual(parseListenerPids(NETSTAT, 'win32', 8765), ['111']);
});

test('command-line lookup only ever interpolates digits', () => {
  assert.equal(commandLineCommand('linux', '12; rm -rf /'), 'ps -p 12 -o command=');
  assert.ok(commandLineCommand('win32', '77').includes("ProcessId=77"));
});

test('the Auralis backend is recognised by command line, other servers are not', () => {
  for (const ours of [
    '/opt/Auralis/resources/backend/auralis-backend',
    'python /home/u/src/matchering/auralis-web/backend/main.py',
    'C:\\Program Files\\Auralis\\resources\\backend\\auralis-backend.exe',
    'python3 /opt/Auralis/resources/backend/main.py',
  ]) {
    assert.equal(isAuralisBackendCommand(ours), true, ours);
  }
  for (const other of ['', 'node vite --port 8765', 'python -m http.server 8765', '/usr/bin/chrome --type=utility']) {
    assert.equal(isAuralisBackendCommand(other), false, other);
  }
});

test('findListeners splits the listeners into backend and foreign and never lists clients', async () => {
  const answers = {
    [listenCommand('linux', 8765)]: '111\n222\n',
    [commandLineCommand('linux', '111')]: 'python /src/auralis-web/backend/main.py --dev\n',
    [commandLineCommand('linux', '222')]: 'node /srv/other-server.js\n',
  };
  const seen = [];
  const exec = (command, callback) => {
    seen.push(command);
    callback(command in answers ? null : new Error('unexpected'), answers[command] || '');
  };

  const result = await findListeners({ exec, platform: 'linux', port: 8765 });

  assert.deepEqual(result, { backend: ['111'], foreign: ['222'] });
  assert.ok(seen.every((command) => !/kill/.test(command)));
});

test('no listener means nothing to stop', async () => {
  const exec = (command, callback) => callback(new Error('lsof exits 1 when nothing matches'), '');

  assert.deepEqual(await findListeners({ exec, platform: 'linux', port: 8765 }), { backend: [], foreign: [] });
});

test('stopProcess terminates a polite process with SIGTERM', async () => {
  const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore' });
  const exited = new Promise((resolve) => child.on('exit', (code, signal) => resolve(signal)));

  assert.equal(await stopProcess(child.pid, { graceMs: 3000 }), true);
  assert.equal(await exited, 'SIGTERM');
});

test('stopProcess escalates to SIGKILL for a process that ignores SIGTERM', async () => {
  const child = spawn(
    process.execPath,
    ['-e', "process.on('SIGTERM', () => {}); console.log('ready'); setInterval(() => {}, 1000)"],
    { stdio: ['ignore', 'pipe', 'ignore'] }
  );
  const exited = new Promise((resolve) => child.on('exit', (code, signal) => resolve(signal)));
  await new Promise((resolve) => child.stdout.once('data', resolve));

  assert.equal(await stopProcess(child.pid, { graceMs: 300, pollMs: 50 }), true);
  assert.equal(await exited, 'SIGKILL');
});

test('main.js takes the single-instance lock and handles second-instance', () => {
  const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');

  assert.match(main, /app\.requestSingleInstanceLock\(\)/);
  assert.match(main, /app\.on\(\s*'second-instance'/);
  assert.doesNotMatch(main, /kill -9|taskkill \/F/);
});

test('port-cleanup.js ships in the packaged app', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));

  assert.ok(pkg.build.files.includes('port-cleanup.js'));
});
