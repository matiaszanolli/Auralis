#!/usr/bin/env node

const { spawn } = require('node:child_process');
const path = require('node:path');

// Keep the root pnpm command as an alias for the same source supervisor.
const python = process.env.AURALIS_PYTHON || 'python';
const child = spawn(python, [path.join(__dirname, 'launch-auralis-web.py'), '--electron', ...process.argv.slice(2)], {
  cwd: __dirname,
  stdio: 'inherit',
  detached: process.platform !== 'win32',
});

child.on('error', (error) => {
  console.error(`Could not start the Auralis launcher with ${python}: ${error.message}`);
  process.exitCode = 1;
});
child.on('exit', (code) => {
  process.exitCode = code ?? 1;
});
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    // Windows delivers Ctrl+C to Python through the shared console.
    if (process.platform !== 'win32' || signal !== 'SIGINT') child.kill(signal);
  });
}
