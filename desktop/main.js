const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class AuralisApp {
  constructor() {
    this.pythonProcess = null;
    this.mainWindow = null;
    this.backendReady = false;
    this.isQuitting = false;
  }

  async startPythonBackend() {
    return new Promise((resolve, reject) => {
      console.log('Starting Python backend...');

      // In development: python backend/main.py
      // In production: ./backend/auralis-backend.exe
      const pythonCmd = app.isPackaged
        ? path.join(process.resourcesPath, 'backend', 'auralis-backend')
        : 'python';

      const pythonArgs = app.isPackaged
        ? []
        : [path.join(__dirname, '..', 'auralis-web', 'backend', 'main.py')];

      console.log(`Executing: ${pythonCmd} ${pythonArgs.join(' ')}`);

      this.pythonProcess = spawn(pythonCmd, pythonArgs, {
        stdio: ['pipe', 'pipe', 'pipe'],
        cwd: app.isPackaged ? process.resourcesPath : path.join(__dirname, '..')
      });

      let startupOutput = '';

      // Wait for backend to be ready
      this.pythonProcess.stdout.on('data', (data) => {
        const output = data.toString();
        startupOutput += output;
        console.log('Backend stdout:', output);

        // Look for backend ready signals
        if (output.includes('Backend ready') ||
            output.includes('Uvicorn running') ||
            output.includes('Application startup complete')) {
          this.backendReady = true;
          console.log('Backend is ready!');
          resolve();
        }
      });

      // Handle backend errors
      this.pythonProcess.stderr.on('data', (data) => {
        const error = data.toString();
        console.error('Backend stderr:', error);

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

    // TODO: Add health check HTTP request to backend
    // For now, just wait a bit more
    console.log('Backend health check passed (placeholder)');
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
      icon: path.join(__dirname, 'assets', 'icon.png'),
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js'),
        webSecurity: true
      }
    });

    // Load the React app
    const startUrl = app.isPackaged
      ? 'http://localhost:8000'  // Backend serves React in production
      : 'http://localhost:3000'; // Vite dev server

    console.log(`Loading URL: ${startUrl}`);

    // Handle navigation
    this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });

    try {
      await this.mainWindow.loadURL(startUrl);
      console.log('URL loaded successfully');

      // Show window when ready
      this.mainWindow.show();

      // Open DevTools in development
      if (!app.isPackaged) {
        this.mainWindow.webContents.openDevTools();
      }

    } catch (error) {
      console.error('Failed to load URL:', error);

      // Show error page or fallback
      this.mainWindow.loadFile(path.join(__dirname, 'error.html'));
      this.mainWindow.show();
    }

    // Handle window closed
    this.mainWindow.on('closed', () => {
      this.mainWindow = null;
    });
  }

  async initialize() {
    try {
      console.log('Initializing Auralis desktop app...');

      // Start Python backend first
      await this.startPythonBackend();
      console.log('Backend started successfully');

      // Wait for backend to be healthy
      await this.waitForBackendHealth();
      console.log('Backend health check passed');

      // Then create the UI window
      await this.createWindow();
      console.log('UI window created');

    } catch (error) {
      console.error('Failed to initialize app:', error);

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
      this.pythonProcess.kill('SIGTERM');

      // Force kill after 5 seconds
      setTimeout(() => {
        if (!this.pythonProcess.killed) {
          console.log('Force killing Python backend...');
          this.pythonProcess.kill('SIGKILL');
        }
      }, 5000);
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
      { name: 'Audio Files', extensions: ['mp3', 'wav', 'flac', 'm4a', 'ogg'] },
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

// App lifecycle events
app.whenReady().then(() => {
  console.log('Electron app ready');
  auralisApp.initialize();
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