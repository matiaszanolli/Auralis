const { app, BrowserWindow, dialog, ipcMain, session, shell } = require('electron');
const { autoUpdater } = require('electron-updater');
const log = require('electron-log/main');
const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const { setTimeout: delay } = require('node:timers/promises');
const path = require('node:path');
const fs = require('node:fs');
const { isSafeExternalUrl, isAllowedAppNavigation, isTrustedIpcSender, escapeControlChars, backendLogLines, DEV_ORIGIN_FLAG, APP_PORT, APP_ORIGIN, DEV_ORIGIN } = require('./url-safety');
const { buildBackendEnv } = require('./backend-env');
const { terminateBackend } = require('./backend-shutdown');
const { DIGEST_FILE, verifyBackendBinary } = require('./backend-integrity');
const STARTUP_TIMEOUT_MS = 45000;
// Allow the backend's bounded lifespan shutdown to flush its SQLite WAL and stop workers.
const BACKEND_KILL_GRACE_MS = 40000;

// Configure logging for auto-updater
log.transports.file.level = 'info';

// Owner-only log file (#4932). electron-log's file transport defaults to
// requesting mode 0o666, so the file lands at 0o666 & ~umask — 0o644 under the
// usual 0o022, i.e. world-readable. That is harmless under this app's
// single-user desktop threat model and while the file holds only update-check
// timestamps, but #4920 has since begun routing backend output through this
// same file, so its contents are no longer trivially uninteresting. 0o600
// costs nothing and stops the question recurring.
//
// Merged onto the transport's existing writeOptions rather than replaced:
// assigning a bare { mode } would drop the upstream flag:'a' and
// encoding:'utf8' defaults, truncating the log on every launch.
log.transports.file.writeOptions = {
  ...log.transports.file.writeOptions,
  mode: 0o600,
};

autoUpdater.logger = log;

/**
 * Single validated path to the OS shell for any navigation the renderer
 * tries to open externally — both setWindowOpenHandler call sites below
 * route through this instead of calling shell.openExternal directly (#4844).
 */
function openExternalSafely(url) {
  if (!isSafeExternalUrl(url)) {
    log.warn(`Blocked shell.openExternal for disallowed URL: ${escapeControlChars(url)}`);
    return;
  }
  shell.openExternal(url);
}

class AuralisApp {
  constructor() {
    this.pythonProcess = null;
    this.mainWindow = null;
    this.isQuitting = false;
    this.isDevelopment = !app.isPackaged;
    this.backendPort = this.isDevelopment ? Number(process.env.AURALIS_PORT) : APP_PORT;
    this.launchId = this.isDevelopment ? process.env.AURALIS_LAUNCH_ID : randomUUID();
    this.initializing = false;
    this.initialized = false;
  }

  startPythonBackend() {
    if (!fs.existsSync(path.join(process.resourcesPath, 'frontend', 'index.html'))) {
      throw new Error('The installed frontend is missing. Reinstall Auralis.');
    }
    let pythonCmd, pythonArgs;
    const isWindows = process.platform === 'win32';
    const cwd = path.join(process.resourcesPath, 'backend');
    const backendPath = path.join(cwd, 'auralis-backend');
    const backendExe = isWindows ? `${backendPath}.exe` : backendPath;

    // Only the bundled binary, and only once it matches the digest recorded at build time (#6527).
    // The python3 script fallback ran whatever interpreter and sources were on disk. macOS is
    // exempt from the digest: codesign rewrites the binary after it is recorded, and there the
    // backend sits inside the signed bundle, whose signature covers it.
    if (!fs.existsSync(backendExe)) {
      throw new Error('The installed backend is missing. Reinstall Auralis.');
    }
    if (process.platform !== 'darwin') verifyBackendBinary(backendExe, path.join(__dirname, DIGEST_FILE));
    pythonCmd = backendExe;
    pythonArgs = [];
    this.pythonProcess = spawn(pythonCmd, pythonArgs, {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: process.platform !== 'win32',
      env: {
        ...buildBackendEnv(process.env, false),
        AURALIS_LAUNCH_ID: this.launchId,
        PYTHONUNBUFFERED: '1',
        ELECTRON_MODE: '1',
        PYTHONPATH: process.resourcesPath,
      },
    });

    // Line by line, escaped, at each line's own Python level (#6540).
    const pipeBackend = (fallbackLevel) => (output) => {
      for (const { level, line } of backendLogLines(output, fallbackLevel)) log[level]('[Backend]', line);
    };
    this.pythonProcess.stdout.on('data', pipeBackend('info'));
    this.pythonProcess.stderr.on('data', pipeBackend('error'));
    this.pythonProcess.on('error', (error) => {
      this.backendSpawnError = error;
      log.error('Failed to start backend:', error);
    });
    this.pythonProcess.on('exit', (code, signal) => {
      if (this.initialized && !this.isQuitting) {
        this.failStartup(new Error(`Backend stopped (${code ?? signal}).`));
      }
    });
  }

  async waitForBackend() {
    const deadline = Date.now() + STARTUP_TIMEOUT_MS;
    while (!this.isQuitting && Date.now() < deadline) {
      if (this.backendSpawnError) throw this.backendSpawnError;
      const child = this.pythonProcess;
      if (child && (child.exitCode !== null || child.signalCode !== null)) {
        throw new Error(`Backend exited (${child.exitCode ?? child.signalCode}) on port ${this.backendPort}.`);
      }
      const response = await fetch(`http://127.0.0.1:${this.backendPort}/api/ready`, {
        redirect: 'error',
        signal: AbortSignal.timeout(1000),
      }).catch(() => null);
      if (response) {
        await response.body?.cancel();
        if (response.headers.get('X-Auralis-Launch-Id') === this.launchId) {
          if (response.ok) return;
          if (response.status === 503) throw new Error('The backend could not initialize.');
        }
      }
      await delay(100);
    }
    throw new Error(`Backend did not become ready on port ${this.backendPort}.`);
  }

  async createWindow() {
    console.log('Creating main window...');

    this.mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 800,
      minHeight: 600,
      show: false, // Don't show until ready
      titleBarStyle: 'default',
      backgroundColor: '#1a1a1a',
      icon: path.join(__dirname, 'assets', 'icon.png'),
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
        preload: path.join(__dirname, 'preload.js'),
        // Lets the preload expose electronAPI to the Vite dev origin only
        // when unpackaged (#5356); the packaged app gets the app origin alone.
        additionalArguments: this.isDevelopment ? [DEV_ORIGIN_FLAG] : [],
        webSecurity: true
      }
    });

    const window = this.mainWindow;
    window.on('closed', () => { this.mainWindow = null; });
    window.webContents.setWindowOpenHandler(({ url }) => {
      openExternalSafely(url);
      return { action: 'deny' };
    });

    // loadURL rejects on renderer load failure. Keep the window hidden until
    // it has loaded the frontend selected by this launch mode.
    await window.loadURL(this.isDevelopment ? DEV_ORIGIN : APP_ORIGIN);
    window.show();
    if (this.isDevelopment) window.webContents.openDevTools();
  }

  async initialize() {
    if (this.initializing || this.isQuitting) return;
    this.initializing = true;
    try {
      if (!this.initialized) {
        if (this.isDevelopment) {
          if (!this.launchId || !Number.isInteger(this.backendPort) ||
              this.backendPort < 1 || this.backendPort > 65535) {
            throw new Error('Start Electron development with pnpm run dev from the repository root.');
          }
        } else {
          this.startPythonBackend();
        }
        await this.waitForBackend();
      }
      if (this.isQuitting) return;
      await this.createWindow();
      this.initialized = true;
      console.log('Auralis is ready');
    } catch (error) {
      if (!this.isQuitting) await this.failStartup(error);
    } finally {
      this.initializing = false;
    }
  }

  async failStartup(error) {
    log.error('Auralis startup failed:', error);
    if (!this.isDevelopment) dialog.showErrorBox('Auralis startup failed', error.message);
    await this.cleanup().catch((cleanupError) => log.error('Backend cleanup failed:', cleanupError));
    app.exit(1);
  }

  /**
   * Stop the backend; resolves once it has exited or been SIGKILLed after BACKEND_KILL_GRACE_MS.
   * Callers that are about to quit must wait for it: the escalation timer dies with the app (#5992).
   */
  cleanup() {
    if (this.cleanupPromise) return this.cleanupPromise;
    this.isQuitting = true;
    this.cleanupPromise = terminateBackend(this.pythonProcess, {
      graceMs: BACKEND_KILL_GRACE_MS,
      killGroup: (pid) => process.kill(-pid, 'SIGKILL'),
      log: (message) => console.log(message),
    });
    return this.cleanupPromise;
  }
}

// Initialize app instance
const auralisApp = new AuralisApp();

// Every handler refuses a caller that is not the app's own top-level document (#6174).
function handleTrusted(channel, handler) {
  ipcMain.handle(channel, (event, ...args) => {
    if (!isTrustedIpcSender(event, { isDevelopment: !app.isPackaged })) {
      log.warn(`Refused IPC '${channel}' from untrusted frame: ${escapeControlChars(String(event.senderFrame && event.senderFrame.url))}`);
      throw new Error('Untrusted IPC sender');
    }
    return handler(event, ...args);
  });
}

// Set up IPC handlers
handleTrusted('select-file', async () => {
  const result = await dialog.showOpenDialog(auralisApp.mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Audio Files', extensions: ['mp3', 'wav', 'flac', 'm4a', 'ogg', 'aac'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });
  return result.filePaths;
});

handleTrusted('select-folder', async () => {
  const result = await dialog.showOpenDialog(auralisApp.mainWindow, {
    properties: ['openDirectory']
  });
  return result.filePaths;
});

handleTrusted('window-minimize', () => {
  if (auralisApp.mainWindow) {
    auralisApp.mainWindow.minimize();
  }
});

handleTrusted('window-maximize', () => {
  if (auralisApp.mainWindow) {
    if (auralisApp.mainWindow.isMaximized()) {
      auralisApp.mainWindow.unmaximize();
    } else {
      auralisApp.mainWindow.maximize();
    }
  }
});

handleTrusted('window-close', () => {
  if (auralisApp.mainWindow) {
    auralisApp.mainWindow.close();
  }
});

// Configure auto-updater
autoUpdater.autoDownload = false; // Ask user before downloading
autoUpdater.autoInstallOnAppQuit = true;

// Auto-updater event handlers
autoUpdater.on('checking-for-update', () => {
  log.info('Checking for updates...');
});

autoUpdater.on('update-available', (info) => {
  log.info('Update available:', info.version);

  // Show update notification to user
  if (auralisApp.mainWindow) {
    dialog.showMessageBox(auralisApp.mainWindow, {
      type: 'info',
      title: 'Update Available',
      message: `A new version (${info.version}) is available!`,
      detail: 'Would you like to download and install it? The app will restart after installation.',
      buttons: ['Download Update', 'Later'],
      defaultId: 0,
      cancelId: 1
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.downloadUpdate();
      }
    });
  }
});

autoUpdater.on('update-not-available', (info) => {
  log.info('Update not available. Current version:', info.version);
});

autoUpdater.on('error', (err) => {
  log.error('Auto-updater error:', err);
});

autoUpdater.on('download-progress', (progressObj) => {
  let logMessage = `Download speed: ${progressObj.bytesPerSecond} - Downloaded ${progressObj.percent}%`;
  logMessage = `${logMessage} (${progressObj.transferred}/${progressObj.total})`;
  log.info(logMessage);

  // Update UI with progress (could send to renderer via IPC)
  if (auralisApp.mainWindow) {
    auralisApp.mainWindow.webContents.send('download-progress', progressObj);
  }
});

autoUpdater.on('update-downloaded', (info) => {
  log.info('Update downloaded:', info.version);

  // Notify user that update is ready
  if (auralisApp.mainWindow) {
    dialog.showMessageBox(auralisApp.mainWindow, {
      type: 'info',
      title: 'Update Ready',
      message: 'Update downloaded successfully!',
      detail: 'The update will be installed when you quit the application. Restart now?',
      buttons: ['Restart Now', 'Later'],
      defaultId: 0,
      cancelId: 1
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.quitAndInstall();
      }
    });
  }
});

// IPC handler for manual update check
handleTrusted('check-for-updates', async () => {
  if (!app.isPackaged) {
    return { available: false, message: 'Updates only available in packaged app' };
  }

  try {
    const result = await autoUpdater.checkForUpdates();
    return { available: true, version: result?.updateInfo?.version };
  } catch (error) {
    log.error('Error checking for updates:', error);
    return { available: false, error: error.message };
  }
});

// Single-instance lock (#6157): a second launch used to SIGKILL the first
// instance's live backend while "freeing" the port. Quit it instead and
// bring the first window forward.
const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
  if (app.isPackaged) app.quit();
  else app.exit(1);
} else {
  app.on('second-instance', () => {
    const win = auralisApp.mainWindow;
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });
}

// App lifecycle events
app.whenReady().then(() => {
  if (!hasSingleInstanceLock) return; // quitting: another instance owns the backend
  console.log('Electron app ready');
  // The renderer needs no web permission (no camera, microphone, notifications, geolocation or
  // clipboard-read use anywhere in the frontend), so every request and check is refused (#6174).
  session.defaultSession.setPermissionRequestHandler((_contents, permission, callback) => {
    log.warn(`Denied web permission request: ${escapeControlChars(String(permission))}`);
    callback(false);
  });
  session.defaultSession.setPermissionCheckHandler(() => false);
  auralisApp.initialize();

  // Check for updates on startup (only in production)
  if (app.isPackaged) {
    setTimeout(() => {
      log.info('Checking for updates on startup...');
      autoUpdater.checkForUpdates().catch(err => {
        log.error('Failed to check for updates:', err);
      });
    }, 3000); // Wait 3 seconds after startup
  }
});

app.on('window-all-closed', () => {
  console.log('All windows closed');
  if (process.platform !== 'darwin') {
    app.quit(); // before-quit stops the backend and waits for it
  }
});

app.on('activate', () => {
  console.log('App activated');
  if (BrowserWindow.getAllWindows().length === 0) {
    auralisApp.initialize();
  }
});

app.on('before-quit', (event) => {
  console.log('App before quit');
  if (auralisApp.canQuit) return;
  event.preventDefault();
  auralisApp.cleanup().then(() => {
    auralisApp.canQuit = true;
    app.quit();
  }).catch((error) => {
    log.error('Backend cleanup failed:', error);
    app.exit(1);
  });
});

// Security: Prevent new window creation (Electron 12+ API)
app.on('web-contents-created', (_event, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    openExternalSafely(url);
    return { action: 'deny' };
  });

  // setWindowOpenHandler only governs *new* windows. In-place top-level
  // navigation of an existing window has no default restriction: with no
  // will-navigate listener Electron just goes wherever it is pointed, and
  // because preload.js is attached to the BrowserWindow rather than to a URL
  // it re-runs there, handing the whole electronAPI IPC surface to that
  // origin (#4858). Registered on web-contents-created so every webContents
  // is covered, not only mainWindow.
  //
  // will-redirect is needed as well: a 3xx to an off-origin destination does
  // not re-emit will-navigate, so checking only the latter would let a
  // redirect chain walk straight out of localhost.
  const blockOffOrigin = (event, url) => {
    // `!app.isPackaged` is how the rest of main.js decides dev mode (line 32);
    // NODE_ENV is not set in a packaged build, so reusing it here would keep
    // the :3000 dev origin allowed in production.
    if (isAllowedAppNavigation(url, { isDevelopment: !app.isPackaged })) {
      return;
    }
    event.preventDefault();
    log.warn(`Blocked in-window navigation to non-app origin: ${escapeControlChars(url)}`);
    // Treat it the way a clicked external link is treated — the user's
    // browser, not this window, subject to the same scheme allowlist.
    openExternalSafely(url);
  };

  contents.on('will-navigate', blockOffOrigin);
  contents.on('will-redirect', blockOffOrigin);
});
