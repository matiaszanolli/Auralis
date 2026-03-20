/**
 * Typed helpers for the Electron preload bridge.
 *
 * The `electronAPI` shape is declared in `vite-env.d.ts` via Window
 * interface augmentation so all access is type-safe.
 */

/** Whether the app is running inside Electron. */
export function isElectron(): boolean {
  return window.electronAPI !== undefined;
}

/** Returns the typed bridge, or `undefined` in the browser. */
export function getElectronAPI(): ElectronAPI | undefined {
  return window.electronAPI;
}
