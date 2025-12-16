const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const { autoUpdater } = require('electron-updater');
const log = require('electron-log');
const { spawn, exec } = require('child_process');
const path = require('path');
const fs = require('fs');

// Configure logging for auto-updater
log.transports.file.level = 'info';
autoUpdater.logger = log;

class AuralisApp {
  constructor() {
    this.pythonProcess = null;
    this.mainWindow = null;
    this.backendReady = false;
    this.isQuitting = false;
    this.isDevelopment = !app.isPackaged;
    this.backendPort = 8765;
  }

  /**
   * Check if port is in use and kill any process using it
   * Cross-platform: works on Linux, macOS, and Windows
   */
  async cleanupPort() {
    return new Promise((resolve) => {
      console.log(`Checking if port ${this.backendPort} is available...`);

      // Platform-specific commands to find process using port
      const isWindows = process.platform === 'win32';
      const findCommand = isWindows
        ? `netstat -ano | findstr :${this.backendPort}`
        : `lsof -ti:${this.backendPort}`;

      exec(findCommand, (error, stdout, stderr) => {
        if (error || !stdout.trim()) {
          // No process found or command failed, port is free
          console.log(`✓ Port ${this.backendPort} is available`);
          resolve();
          return;
        }

        let pids = [];
        if (isWindows) {
          // Parse netstat output: "TCP    0.0.0.0:8765    0.0.0.0:0    LISTENING    12345"
          const lines = stdout.trim().split('\n');
          pids = lines
            .map(line => {
              const match = line.trim().match(/\s+(\d+)\s*$/);
              return match ? match[1] : null;
            })
            .filter(pid => pid);
          // Remove duplicates
          pids = [...new Set(pids)];
        } else {
          // lsof output: one PID per line
          pids = stdout.trim().split('\n').filter(pid => pid);
        }

        if (pids.length === 0) {
          console.log(`✓ Port ${this.backendPort} is available`);
          resolve();
          return;
        }

        console.log(`⚠️ Found ${pids.length} process(es) using port ${this.backendPort}: ${pids.join(', ')}`);

        // Kill all processes
        const killPromises = pids.map(pid => {
          return new Promise((killResolve) => {
            const killCommand = isWindows ? `taskkill /F /PID ${pid}` : `kill ${pid}`;
            exec(killCommand, (killError) => {
              if (killError) {
                console.error(`Failed to kill process ${pid}:`, killError.message);
              } else {
                console.log(`✓ Killed process ${pid}`);
              }
              killResolve();
            });
          });
        });

        Promise.all(killPromises).then(() => {
          // Wait a bit for processes to fully terminate
          setTimeout(() => {
            console.log(`✓ Port ${this.backendPort} cleanup complete`);
            resolve();
          }, 1000);
        });
      });
    });
  }

  async startPythonBackend() {
    return new Promise(async (resolve, reject) => {
      console.log('Starting Python backend...');
      console.log('Development mode:', this.isDevelopment);

      // First, ensure port is free
      await this.cleanupPort();

      let pythonCmd, pythonArgs, cwd;

      if (this.isDevelopment) {
        // Development: Run Python script directly
        pythonCmd = 'python';
        pythonArgs = [path.join(__dirname, '..', 'auralis-web', 'backend', 'main.py')];
        cwd = path.join(__dirname, '..');
      } else {
        // Production: Run Python backend from resources
        // Platform-specific backend selection
        const isWindows = process.platform === 'win32';
        const backendPath = path.join(process.resourcesPath, 'backend', 'auralis-backend');
        const backendExe = isWindows ? `${backendPath}.exe` : backendPath;
        const pythonScript = path.join(process.resourcesPath, 'backend', 'main.py');

        if (fs.existsSync(backendExe)) {
          // Use compiled binary if available
          pythonCmd = backendExe;
          pythonArgs = [];
          cwd = path.join(process.resourcesPath, 'backend');
        } else if (!isWindows && fs.existsSync(pythonScript)) {
          // macOS/Linux: Fallback to Python script from resources
          console.log('Binary not found, using Python script from resources');
          pythonCmd = 'python3';
          pythonArgs = [pythonScript];
          cwd = path.join(process.resourcesPath, 'backend');
        } else {
          // Error: Backend not available
          const errorMessage = isWindows
            ? `Auralis backend not found.\n\nPlease reinstall Auralis.\n\nAlternatively, install Python 3.13+:\nhttps://python.org`
            : `Backend not found. Tried:\n  Binary: ${backendExe}\n  Script: ${pythonScript}`;

          console.error(errorMessage);

          if (isWindows) {
            // Show user-friendly dialog for Windows
            dialog.showErrorBox('Backend Not Found', errorMessage);
          }

          reject(new Error('Backend executable or script not found'));
          return;
        }
      }

      console.log(`Executing: ${pythonCmd} ${pythonArgs.join(' ')}`);
      console.log(`Working directory: ${cwd}`);

      // Set up Python path to include auralis package
      const pythonPath = this.isDevelopment
        ? path.join(__dirname, '..')
        : process.resourcesPath;

      const fullPythonPath = pythonPath + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : '');
      console.log(`Python path for auralis: ${pythonPath}`);
      console.log(`Full PYTHONPATH: ${fullPythonPath}`);
      console.log(`Is development mode: ${this.isDevelopment}`);

      this.pythonProcess = spawn(pythonCmd, pythonArgs, {
        stdio: ['pipe', 'pipe', 'pipe'],
        cwd: cwd,
        detached: true,  // Create new process group for easy cleanup
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          // Tell backend it's running in Electron
          ELECTRON_MODE: '1',
          // Add auralis package to Python path
          PYTHONPATH: fullPythonPath
        }
      });

      let startupOutput = '';

      // Wait for backend to be ready
      this.pythonProcess.stdout.on('data', (data) => {
        const output = data.toString();
        startupOutput += output;
        console.log('[Backend]', output.trim());

        // Look for backend ready signals
        if (output.includes('Backend ready') ||
            output.includes('Uvicorn running') ||
            output.includes('Application startup complete')) {
          this.backendReady = true;
          console.log('✓ Backend is ready!');
          resolve();
        }
      });

      // Handle backend errors
      this.pythonProcess.stderr.on('data', (data) => {
        const error = data.toString();
        console.error('[Backend Error]', error.trim());

        // Don't treat all stderr as errors (some are just logs)
        if (error.includes('ERROR') || error.includes('CRITICAL')) {
          console.error('Critical backend error:', error);
        }
      });

      this.pythonProcess.on('exit', (code, signal) => {
        console.log(`Backend process exited with code ${code}, signal ${signal}`);
        if (code !== 0 && !this.isQuitting) {
          reject(new Error(`Backend exited with code ${code}`));
        }
      });

      this.pythonProcess.on('error', (error) => {
        console.error('Failed to start backend process:', error);
        reject(error);
      });

      // Timeout after 30 seconds
      setTimeout(() => {
        if (!this.backendReady) {
          console.error('Backend startup timeout. Output so far:', startupOutput);
          reject(new Error('Backend startup timeout'));
        }
      }, 30000);
    });
  }

  async waitForBackendHealth() {
    // Give backend a moment to start serving
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Try to ping the health endpoint
    try {
      const http = require('http');
      const options = {
        hostname: 'localhost',
        port: 8765,
        path: '/api/health',
        method: 'GET',
        timeout: 5000
      };

      await new Promise((resolve, reject) => {
        const req = http.request(options, (res) => {
          console.log(`Health check status: ${res.statusCode}`);
          if (res.statusCode === 200) {
            resolve();
          } else {
            reject(new Error(`Health check failed with status ${res.statusCode}`));
          }
        });

        req.on('error', (error) => {
          console.warn('Health check request failed:', error.message);
          // Don't fail completely, just warn
          resolve();
        });

        req.on('timeout', () => {
          console.warn('Health check timed out');
          req.destroy();
          resolve();
        });

        req.end();
      });

      console.log('✓ Backend health check passed');
    } catch (error) {
      console.warn('Backend health check warning:', error.message);
      // Continue anyway - the backend might be ready but not responding to HTTP yet
    }
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
        preload: path.join(__dirname, 'preload.js'),
        webSecurity: true
      }
    });

    // Load the React app
    let startUrl;

    if (this.isDevelopment) {
      // Development: Load from Vite dev server (if running) or backend
      startUrl = 'http://localhost:3000'; // Try React dev server first
    } else {
      // Production: Backend serves the built React app
      startUrl = 'http://localhost:8765';
    }

    console.log(`Loading URL: ${startUrl}`);

    // Handle navigation
    this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });

    try {
      await this.mainWindow.loadURL(startUrl);
      console.log('✓ URL loaded successfully');

      // Show window when ready (with timeout fallback for Linux)
      let windowShown = false;

      this.mainWindow.once('ready-to-show', () => {
        if (!windowShown) {
          windowShown = true;
          this.mainWindow.show();
          console.log('✓ Window shown (ready-to-show event)');
        }
      });

      // Fallback: Force show after 2 seconds if event doesn't fire
      // This fixes display issues on some Linux window managers
      setTimeout(() => {
        if (!windowShown) {
          windowShown = true;
          this.mainWindow.show();
          console.log('✓ Window shown (fallback timeout)');
        }
      }, 2000);

      // Open DevTools in development
      if (this.isDevelopment) {
        this.mainWindow.webContents.openDevTools();
      }

    } catch (error) {
      console.error('Failed to load URL:', error);

      // Try alternative URL if development failed
      if (this.isDevelopment) {
        console.log('Trying backend URL instead...');
        try {
          await this.mainWindow.loadURL('http://localhost:8765');
          this.mainWindow.show();
        } catch (backendError) {
          // Show error page
          this.mainWindow.loadFile(path.join(__dirname, 'error.html'));
          this.mainWindow.show();
        }
      } else {
        // Show error page in production
        this.mainWindow.loadFile(path.join(__dirname, 'error.html'));
        this.mainWindow.show();
      }
    }

    // Handle window closed
    this.mainWindow.on('closed', () => {
      this.mainWindow = null;
    });
  }

  async initialize() {
    try {
      console.log('🚀 Initializing Auralis desktop app...');
      console.log(`Mode: ${this.isDevelopment ? 'Development' : 'Production'}`);
      console.log(`Platform: ${process.platform}`);
      console.log('');

      // Start Python backend first
      console.log('[1/3] Starting backend...');
      await this.startPythonBackend();
      console.log('✓ Backend started');
      console.log('');

      // Wait for backend to be healthy
      console.log('[2/3] Checking backend health...');
      await this.waitForBackendHealth();
      console.log('✓ Backend healthy');
      console.log('');

      // Then create the UI window
      console.log('[3/3] Creating UI window...');
      await this.createWindow();
      console.log('✓ UI ready');
      console.log('');

      console.log('✅ Auralis is ready!');

    } catch (error) {
      console.error('❌ Failed to initialize app:', error);

      dialog.showErrorBox('Startup Error',
        `Failed to start Auralis:\n\n${error.message}\n\nPlease check that Python is installed and try again.`);

      this.cleanup();
      app.quit();
    }
  }

  cleanup() {
    console.log('Cleaning up...');
    this.isQuitting = true;

    if (this.pythonProcess && !this.pythonProcess.killed) {
      console.log('Terminating Python backend...');

      // Try graceful shutdown first
      this.pythonProcess.kill('SIGTERM');

      // Force kill after 2 seconds (reduced from 5)
      setTimeout(() => {
        if (this.pythonProcess && !this.pythonProcess.killed) {
          console.log('Backend still running, sending SIGKILL...');
          this.pythonProcess.kill('SIGKILL');

          // Also try to kill the process tree
          if (this.pythonProcess.pid) {
            try {
              process.kill(-this.pythonProcess.pid, 'SIGKILL');
              console.log('Killed process tree');
            } catch (e) {
              // Ignore errors (process may already be dead)
            }
          }
        }
      }, 2000);
    }

    this.pythonProcess = null;
  }
}

// Initialize app instance
const auralisApp = new AuralisApp();

// Set up IPC handlers
ipcMain.handle('select-file', async () => {
  const result = await dialog.showOpenDialog(auralisApp.mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Audio Files', extensions: ['mp3', 'wav', 'flac', 'm4a', 'ogg', 'aac'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });
  return result.filePaths;
});

ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(auralisApp.mainWindow, {
    properties: ['openDirectory']
  });
  return result.filePaths;
});

ipcMain.handle('window-minimize', () => {
  if (auralisApp.mainWindow) {
    auralisApp.mainWindow.minimize();
  }
});

ipcMain.handle('window-maximize', () => {
  if (auralisApp.mainWindow) {
    if (auralisApp.mainWindow.isMaximized()) {
      auralisApp.mainWindow.unmaximize();
    } else {
      auralisApp.mainWindow.maximize();
    }
  }
});

ipcMain.handle('window-close', () => {
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
ipcMain.handle('check-for-updates', async () => {
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

// App lifecycle events
app.whenReady().then(() => {
  console.log('Electron app ready');
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
  auralisApp.cleanup();
  if (process.platform !== 'darwin') {
    app.quit();
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
  if (!auralisApp.isQuitting) {
    event.preventDefault();
    auralisApp.cleanup();
    setTimeout(() => {
      app.quit();
    }, 1000);
  }
});

// Handle protocol for deep linking (future use)
app.setAsDefaultProtocolClient('auralis');

// Security: Prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (event, navigationUrl) => {
    event.preventDefault();
    require('electron').shell.openExternal(navigationUrl);
  });
});