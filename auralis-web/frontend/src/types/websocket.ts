/**
 * WebSocket message types — barrel.
 * #4081: the former 815-line monolith was split into ./ws/* by domain. This
 * barrel re-exports every module so all `import { ... } from '@/types/websocket'`
 * call sites resolve unchanged.
 */

export * from './ws/base';
export * from './ws/player';
export * from './ws/queue';
export * from './ws/library';
export * from './ws/streaming';
export * from './ws/enhancement';
export * from './ws/registry';
export * from './ws/guards';
