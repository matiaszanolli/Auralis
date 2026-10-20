/**
 * useConnectionStatus color mapping for the full 4-state ConnectionStatus
 * union (#5468): 'error' (permanent failure — retry budget exhausted or a
 * policy close code) must render distinctly from 'connecting', sharing the
 * disconnected red, so a dead connection never displays as an eternal
 * "connecting" spinner.
 */

import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';

import { tokens } from '@/design-system';
import { useConnectionStatus } from '../useConnectionStatus';

describe('useConnectionStatus (#5468)', () => {
  it('maps each connection state to its status token color', () => {
    expect(renderHook(() => useConnectionStatus('connected')).result.current)
      .toBe(tokens.colors.status.connected);
    expect(renderHook(() => useConnectionStatus('connecting')).result.current)
      .toBe(tokens.colors.status.connecting);
    expect(renderHook(() => useConnectionStatus('disconnected')).result.current)
      .toBe(tokens.colors.status.disconnected);
  });

  it('maps a permanently failed connection to the disconnected red, not connecting', () => {
    const error = renderHook(() => useConnectionStatus('error')).result.current;
    expect(error).toBe(tokens.colors.status.disconnected);
    expect(error).not.toBe(tokens.colors.status.connecting);
  });
});
