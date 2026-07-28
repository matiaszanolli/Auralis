/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_COMMIT_ID: string
  /** Overrides API_BASE_URL in config/api.ts and standardizedAPIClient (#4468). */
  readonly VITE_API_URL?: string
  /** Overrides WS_BASE_URL in config/api.ts (#4468). */
  readonly VITE_WS_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/** Electron preload bridge exposed via contextBridge. */
interface ElectronAPI {
  selectFolder(): Promise<string[] | null>;
}

interface Window {
  electronAPI?: ElectronAPI;
}
