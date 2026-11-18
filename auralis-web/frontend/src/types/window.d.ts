/**
 * Global Window type extensions for Auralis
 *
 * Provides type-safe access to global properties attached to `window`,
 * eliminating `(window as any)` casts throughout the codebase.
 */

interface AuralisDebugInfo {
  commitId: string;
  buildMode: string;
  version: string;
}

declare global {
  interface Window {
    // Audio engine singletons
    __auralisAnalyser?: AnalyserNode;
    __auralisAudioContext?: AudioContext;

    // Debug/diagnostic globals
    __AURALIS_DEBUG__?: AuralisDebugInfo;
  }
}

export {};
