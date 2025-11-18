/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_COMMIT_ID: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
