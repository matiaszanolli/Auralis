const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // File system operations
  selectFile: () => ipcRenderer.invoke('select-file'),
  selectFolder: () => ipcRenderer.invoke('select-folder'),

  // Window control
  minimize: () => ipcRenderer.invoke('window-minimize'),
  maximize: () => ipcRenderer.invoke('window-maximize'),
  close: () => ipcRenderer.invoke('window-close'),

  // Backend communication (if needed beyond HTTP)
  sendToBackend: (data) => ipcRenderer.invoke('backend-message', data),

  // Platform info
  platform: process.platform,
  isPackaged: process.env.NODE_ENV === 'production',

  // App info
  version: process.env.npm_package_version || '1.0.0',

  // Utility functions
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // Event listeners for app state
  onAppReady: (callback) => {
    ipcRenderer.on('app-ready', callback);
  },

  onBackendReady: (callback) => {
    ipcRenderer.on('backend-ready', callback);
  },

  onAppError: (callback) => {
    ipcRenderer.on('app-error', callback);
  },

  // Remove listeners
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  }
});

// Log that preload script has loaded
console.log('Auralis preload script loaded');
console.log('Platform:', process.platform);
console.log('Node version:', process.versions.node);
console.log('Electron version:', process.versions.electron);