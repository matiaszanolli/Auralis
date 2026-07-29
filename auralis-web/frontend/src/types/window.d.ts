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

interface AuralisPerformanceInfo {
  selectors: unknown;
  rendering: unknown;
  bundle: unknown;
}

interface AuralisA11yInfo {
  audit: unknown;
  focus: unknown;
  contrast: unknown;
  liveRegions: unknown;
}

declare global {
  interface Window {
    // Audio engine singletons
    __auralisAnalyser?: AnalyserNode;
    __auralisAudioContext?: AudioContext;

    // Debug/diagnostic globals
    __AURALIS_DEBUG__?: AuralisDebugInfo;
    __AURALIS_PERFORMANCE__?: AuralisPerformanceInfo;
    __A11Y__?: AuralisA11yInfo;

    // Vendor prefixed APIs
    // #4623: webkitAudioContext removed — nothing reads it, and declaring it
    // is what let the dead `window.AudioContext || window.webkitAudioContext`
    // fallbacks keep compiling.
    msCrypto?: Crypto;
  }
}

export {};
