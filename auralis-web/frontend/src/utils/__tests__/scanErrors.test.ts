import { describe, it, expect } from 'vitest';
import { APIRequestError } from '@/utils/apiRequestTypes';
import { describeScanError } from '../scanErrors';

describe('describeScanError (#5914)', () => {
  it('treats 409 as informational and keeps the backend detail', () => {
    expect(describeScanError(new APIRequestError('x', 409, 'Scan already in progress'))).toEqual({
      message: 'Scan already in progress',
      informational: true,
    });
  });

  it('falls back to a fixed message when a 409 carries no detail', () => {
    expect(describeScanError(new APIRequestError('x', 409)).message).toBe('Scan already in progress');
  });

  it.each([
    [429, 'Too many requests'],
    [504, 'Library scan timed out after 1800s'],
    [500, 'Internal error'],
  ])('shows the backend detail for a %i', (status, detail) => {
    expect(describeScanError(new APIRequestError('x', status, detail))).toEqual({
      message: `Scan failed: ${detail}`,
      informational: false,
    });
  });

  it('says "Unknown error" for an HTTP failure without a detail', () => {
    expect(describeScanError(new APIRequestError('x', 500)).message).toBe('Scan failed: Unknown error');
  });

  it('reports a transport failure (status 0) as an unreachable backend', () => {
    expect(describeScanError(new APIRequestError('timeout', 0))).toEqual({
      message: 'Error scanning folder — check the backend is reachable',
      informational: false,
    });
    expect(describeScanError(new TypeError('Failed to fetch')).informational).toBe(false);
  });
});
