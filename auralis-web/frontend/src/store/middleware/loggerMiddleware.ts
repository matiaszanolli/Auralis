/**
 * Redux Logger Middleware
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Development middleware for debugging Redux state changes.
 * Logs action types, payloads, and state diffs in development.
 *
 * Features:
 * - Automatic action logging with timestamps
 * - State diff visualization
 * - Action duration tracking
 * - Selective logging by action type
 * - Collapsible console groups for readability
 * - Performance metrics
 *
 * Phase C.4d: Redux Middleware Utilities
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import type { Middleware, UnknownAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';

// ============================================================================
// Logger Configuration
// ============================================================================

export interface LoggerConfig {
  enabled?: boolean;
  collapsed?: boolean;
  duration?: boolean;
  timestamps?: boolean;
  colors?: boolean;
  diff?: boolean;
  predicate?: (getState: () => RootState, action: UnknownAction) => boolean;
  actionSanitizer?: (action: UnknownAction) => UnknownAction;
  stateSanitizer?: (state: RootState) => RootState;
  ignoredActions?: string[];
  onlyActions?: string[];
}

const defaultConfig: LoggerConfig = {
  enabled: process.env.NODE_ENV === 'development',
  collapsed: true,
  duration: true,
  timestamps: true,
  colors: true,
  diff: true,
  predicate: undefined,
  actionSanitizer: (action) => action,
  stateSanitizer: (state) => state,
  ignoredActions: [],
  onlyActions: [],
};

// ============================================================================
// Console Styling
// ============================================================================

const colors = {
  action: '#03A9F4',
  prevState: '#9C27B0',
  nextState: '#4CAF50',
  error: '#F20404',
  duration: '#FF6D00',
};

const style = (color: string) => `color: ${color}; font-weight: bold; font-size: 12px;`;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format timestamp for logging
 */
function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  const timeStr = new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
  const ms = String(date.getMilliseconds()).padStart(3, '0');
  return `${timeStr}.${ms}`;
}

/**
 * Create colored console output
 */
function log(message: string, color: string, ...args: any[]): void {
  if (typeof window !== 'undefined' && window.console) {
    console.log(`%c${message}`, style(color), ...args);
  }
}

/**
 * Deep clone object for state diff
 */
function deepClone(obj: any): any {
  if (typeof obj !== 'object' || obj === null) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(deepClone);
  }

  const cloned: any = {};
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      cloned[key] = deepClone(obj[key]);
    }
  }
  return cloned;
}

/**
 * Calculate state diff
 */
function getStateDiff(prev: RootState, next: RootState): Record<string, any> {
  const diff: Record<string, any> = {};

  // Check each slice
  const slices = Object.keys(next) as (keyof RootState)[];
  for (const slice of slices) {
    if (JSON.stringify(prev[slice]) !== JSON.stringify(next[slice])) {
      diff[slice] = {
        prev: prev[slice],
        next: next[slice],
      };
    }
  }

  return diff;
}

/**
 * Format value for console display
 */
function formatValue(value: any, maxDepth: number = 2): string {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (typeof value === 'string') return `"${value}"`;
  if (typeof value === 'object') {
    if (maxDepth === 0) return '[Object]';
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return '[Circular]';
    }
  }
  return String(value);
}

// ============================================================================
// Logger Middleware Factory
// ============================================================================

/**
 * Create Redux logger middleware
 */
export function createLoggerMiddleware(config: LoggerConfig = {}): Middleware {
  const finalConfig: LoggerConfig = { ...defaultConfig, ...config };

  return (store) => {
    let isDispatching = false;

    return (next) => (action: unknown): unknown => {
      const act = action as UnknownAction;
      // Skip if disabled
      if (!finalConfig.enabled) {
        return next(action);
      }

      // Skip ignored actions
      if (finalConfig.ignoredActions?.includes(act.type)) {
        return next(action);
      }

      // Only log specific actions if onlyActions specified
      if (
        finalConfig.onlyActions &&
        finalConfig.onlyActions.length > 0 &&
        !finalConfig.onlyActions.includes(act.type)
      ) {
        return next(action);
      }

      // Check predicate
      if (finalConfig.predicate && !finalConfig.predicate(store.getState, act)) {
        return next(action);
      }

      const prevState = store.getState();
      const timestamp = new Date();
      const startTime = performance.now();

      // Prevent nested logging
      if (isDispatching) {
        return next(action);
      }

      isDispatching = true;

      let result: any;
      let error: Error | undefined;

      try {
        result = next(action);
      } catch (e) {
        error = e as Error;
      }

      isDispatching = false;

      const nextState = store.getState();
      const duration = performance.now() - startTime;

      // Sanitize if needed
      const sanitizedAction = finalConfig.actionSanitizer?.(act) || act;
      const sanitizedPrevState = finalConfig.stateSanitizer?.(prevState) || prevState;
      const sanitizedNextState = finalConfig.stateSanitizer?.(nextState) || nextState;

      // Log to console
      const groupMethod = finalConfig.collapsed ? 'groupCollapsed' : 'group';
      const titleSuffix = error ? '❌' : '✅';
      const sanitizedAct = sanitizedAction as UnknownAction;

      if (groupMethod === 'groupCollapsed') {
        console.groupCollapsed(
          `${titleSuffix} ${sanitizedAct.type}`,
          finalConfig.timestamps ? `@ ${formatTime(timestamp.getTime())}` : ''
        );
      } else {
        console.group(
          `${titleSuffix} ${sanitizedAct.type}`,
          finalConfig.timestamps ? `@ ${formatTime(timestamp.getTime())}` : ''
        );
      }

      // Log action
      log('Action:', colors.action, sanitizedAct);

      // Log previous state
      if (finalConfig.colors) {
        console.log('%cPrev State:', style(colors.prevState), sanitizedPrevState);
      } else {
        console.log('Prev State:', sanitizedPrevState);
      }

      // Log next state
      if (finalConfig.colors) {
        console.log('%cNext State:', style(colors.nextState), sanitizedNextState);
      } else {
        console.log('Next State:', sanitizedNextState);
      }

      // Log diff
      if (finalConfig.diff) {
        const diff = getStateDiff(sanitizedPrevState, sanitizedNextState);
        if (Object.keys(diff).length > 0) {
          console.log('%c📊 State Diff:', style('#FF9800'), diff);
        }
      }

      // Log duration
      if (finalConfig.duration) {
        const durationColor = duration > 10 ? '#F20404' : colors.duration;
        log(`⏱️ Duration: ${duration.toFixed(2)}ms`, durationColor);
      }

      // Log error if occurred
      if (error) {
        log('❌ Error:', colors.error, error.message);
        console.error(error);
      }

      console.groupEnd();

      if (error) {
        throw error;
      }

      return result;
    };
  };
}

// ============================================================================
// Developer Tools Integration
// ============================================================================

/**
 * Enable Redux DevTools with custom config
 */
export function getDevToolsConfig() {
  return {
    trace: true,
    traceLimit: 25,
    features: {
      pause: true,
      lock: true,
      persist: true,
      export: true,
      import: 'custom',
      jump: true,
      skip: true,
      reorder: true,
      dispatch: true,
      test: true,
    },
  };
}

// ============================================================================
// Exports
// ============================================================================

// LoggerConfig, createLoggerMiddleware, and getDevToolsConfig are exported above
