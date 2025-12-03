/**
 * Auralis Hooks - Organized by Domain
 *
 * Import hooks by category:
 * - hooks/app/* - Global UI state (keyboard, layout, drag/drop)
 * - hooks/player/* - Playback control and queue management
 * - hooks/library/* - Music library access and management
 * - hooks/enhancement/* - Audio mastering and DSP control
 * - hooks/api/* - REST API communication
 * - hooks/websocket/* - Real-time WebSocket communication
 * - hooks/fingerprint/* - Audio fingerprinting and similarity
 * - hooks/shared/* - General utility hooks
 */

// App-level hooks
export * from './app';

// Player hooks
export * from './player';

// Library hooks
export * from './library';

// Enhancement hooks
export * from './enhancement';

// API hooks
export * from './api';

// WebSocket hooks
export * from './websocket';

// Fingerprint hooks
export * from './fingerprint';

// Shared utility hooks
export * from './shared';
