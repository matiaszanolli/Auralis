/**
 * assertNever turns "a union member was added" into a compile error at the switch (#6437);
 * the @ts-expect-error below is that contract, so `pnpm run type-check` is what fails if it drifts.
 */
import { describe, it, expect } from 'vitest';
import { assertNever } from '../assertNever';
import { connectionStatusLabel, type ConnectionStatusType } from '@/components/core/useConnectionStatus';
import { getToastBackgroundColor } from '@/components/shared/Toast/toastColors';

type Shape = 'circle' | 'square';

describe('assertNever', () => {
  it('compiles in an exhaustive switch and fails once a member is left uncovered', () => {
    const exhaustive = (s: Shape): string => {
      switch (s) {
        case 'circle': return 'round';
        case 'square': return 'boxy';
        default: return assertNever(s, 'unknown');
      }
    };
    const missingMember = (s: Shape): string => {
      switch (s) {
        case 'circle': return 'round';
        default:
          // @ts-expect-error -- 'square' is not handled, so `s` is not `never` here
          return assertNever(s, 'unknown');
      }
    };
    expect(exhaustive('square')).toBe('boxy');
    expect(missingMember('square')).toBe('unknown');
  });

  it('returns the fallback for a value that escaped the type system instead of throwing', () => {
    expect(connectionStatusLabel('reconnecting' as ConnectionStatusType)).toBe('Disconnected');
    expect(getToastBackgroundColor('bogus' as Parameters<typeof getToastBackgroundColor>[0])).toBeTruthy();
  });
});
