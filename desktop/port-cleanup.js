'use strict';

// Freeing the backend port before spawning a fresh backend (#6157).
//
// cleanupPort() used to run `lsof -ti:PORT` (Windows: `netstat -ano | findstr
// :PORT`) and `kill -9` / `taskkill /F` every PID it printed. `lsof -i :PORT`
// matches *either end* of a connection, so it also returned clients -- a
// browser tab on localhost:8765, the Vite dev proxy, curl -- and on Windows
// `findstr :8765` is a substring match that also hits `:87650` and the
// foreign-address column. Nothing checked that a PID was the Auralis backend.
//
// Now: only a process LISTENING on the port is considered, and only one whose
// command line is the Auralis backend is stopped, politely (SIGTERM) before
// being forced. Everything that touches the OS goes through an injected `exec`
// so the selection logic is unit-tested without spawning anything.

// The packaged binary is named auralis-backend; the dev and script fallbacks run
// .../auralis-web/backend/main.py or .../resources/backend/main.py.
const BACKEND_COMMAND_PATTERN = /auralis-backend|[\\/]backend[\\/]main\.py/i;

function isAuralisBackendCommand(commandLine) {
  return BACKEND_COMMAND_PATTERN.test(commandLine || '');
}

/** Command that lists only sockets in LISTEN state on `port`. */
function listenCommand(platform, port) {
  return platform === 'win32'
    ? 'netstat -ano -p TCP'
    : `lsof -nP -iTCP:${Number(port)} -sTCP:LISTEN -t`;
}

/** PIDs (strings of digits) of the processes listening on `port`. */
function parseListenerPids(stdout, platform, port) {
  const lines = String(stdout || '').split(/\r?\n/);
  const pids = new Set();
  if (platform === 'win32') {
    // "  TCP    127.0.0.1:8765    0.0.0.0:0    LISTENING    1234" -- anchor on
    // the LOCAL address column so :87650 and foreign addresses do not match.
    const row = new RegExp(`^\\s*TCP\\s+\\S+:${Number(port)}\\s+\\S+\\s+LISTENING\\s+(\\d+)\\s*$`, 'i');
    for (const line of lines) {
      const match = row.exec(line);
      if (match) pids.add(match[1]);
    }
  } else {
    for (const line of lines) {
      if (/^\d+$/.test(line.trim())) pids.add(line.trim());
    }
  }
  return [...pids];
}

/** Command that prints the command line of `pid` (digits only: no shell injection). */
function commandLineCommand(platform, pid) {
  const safePid = String(Number.parseInt(pid, 10));
  return platform === 'win32'
    ? `powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ProcessId=${safePid}').CommandLine"`
    : `ps -p ${safePid} -o command=`;
}

function run(exec, command) {
  return new Promise((resolve) => {
    exec(command, (error, stdout) => resolve(error ? '' : String(stdout || '')));
  });
}

/**
 * PIDs listening on `port` whose command line is the Auralis backend.
 *
 * @param {{exec: Function, platform: string, port: number}} options
 * @returns {Promise<{backend: string[], foreign: string[]}>} `foreign` are
 *   listeners that are NOT ours; they are reported, never killed.
 */
async function findListeners({ exec, platform, port }) {
  const pids = parseListenerPids(await run(exec, listenCommand(platform, port)), platform, port);
  const backend = [];
  const foreign = [];
  for (const pid of pids) {
    const commandLine = await run(exec, commandLineCommand(platform, pid));
    (isAuralisBackendCommand(commandLine) ? backend : foreign).push(pid);
  }
  return { backend, foreign };
}

function isAlive(pid) {
  try {
    process.kill(Number(pid), 0);
    return true;
  } catch (error) {
    return error.code === 'EPERM';
  }
}

/** SIGTERM, wait up to `graceMs` for exit, then SIGKILL. Resolves true if it exited. */
async function stopProcess(pid, { graceMs = 3000, pollMs = 100, sleep } = {}) {
  const wait = sleep || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
  const target = Number(pid);
  try {
    process.kill(target, 'SIGTERM');
  } catch (error) {
    return error.code === 'ESRCH';
  }
  for (let waited = 0; waited < graceMs; waited += pollMs) {
    if (!isAlive(target)) return true;
    await wait(pollMs);
  }
  try {
    process.kill(target, 'SIGKILL');
  } catch (error) {
    return error.code === 'ESRCH';
  }
  await wait(pollMs);
  return !isAlive(target);
}

module.exports = {
  isAuralisBackendCommand,
  listenCommand,
  parseListenerPids,
  commandLineCommand,
  findListeners,
  stopProcess,
};
