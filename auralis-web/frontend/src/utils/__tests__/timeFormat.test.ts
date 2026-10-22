import { describe, it, expect } from 'vitest';
import { formatDuration, formatHoursMinutes, formatHumanDuration } from '@/utils/timeFormat';
import { selectFormattedQueueTime, selectFormattedRemainingTime } from '@/store/selectors';
import { playerSelectors, selectFormattedTime } from '@/store/selectors';
import type { RootState } from '@/store/index';

describe('formatHoursMinutes (#5787)', () => {
  it('short style: "Xh Ym" from an hour up, "Ym" below', () => {
    expect(formatHoursMinutes(4200)).toBe('1h 10m');
    expect(formatHoursMinutes(3600)).toBe('1h 0m');
    expect(formatHoursMinutes(180)).toBe('3m');
    expect(formatHoursMinutes(59)).toBe('0m');
  });

  it('long style matches the album header wording', () => {
    expect(formatHoursMinutes(4200, 'long')).toBe('1 hr 10 min');
    expect(formatHoursMinutes(180, 'long')).toBe('3 min');
  });

  it('never renders NaN for non-finite or negative input', () => {
    for (const bad of [NaN, Infinity, -5]) {
      expect(formatHoursMinutes(bad)).toBe('0m');
      expect(formatHoursMinutes(bad, 'long')).toBe('0 min');
    }
  });
});

describe('formatHumanDuration (#5787)', () => {
  it('keeps the two most significant units, zeros included', () => {
    expect(formatHumanDuration(5025)).toBe('1h 23m');
    expect(formatHumanDuration(3600)).toBe('1h 0m');
    expect(formatHumanDuration(300)).toBe('5m 0s');
    expect(formatHumanDuration(45)).toBe('45s');
    expect(formatHumanDuration(0)).toBe('0s');
  });

  it('floors fractional seconds and guards bad input', () => {
    expect(formatHumanDuration(192.7)).toBe('3m 12s');
    expect(formatHumanDuration(NaN)).toBe('0s');
    expect(formatHumanDuration(-1)).toBe('0s');
  });
});

describe('selectors share the timeFormat helpers (#5787)', () => {
  const state = (over: Record<string, unknown>) => over as unknown as RootState;

  it('selectFormattedTime used to print "NaN:NaN" for NaN; it now matches formatDuration', () => {
    const s = state({ player: { currentTime: NaN, duration: 225 } });
    const out = selectFormattedTime(s);
    expect(out.current).toBe(formatDuration(NaN));
    expect(out.current).not.toContain('NaN');
    expect(out.total).toBe('3:45');
  });

  it('selectFormattedQueueTime formats the total with formatHoursMinutes', () => {
    const s = state({ queue: { tracks: [{ duration: 3000 }, { duration: 1200 }] } });
    expect(selectFormattedQueueTime(s)).toBe('1h 10m');
  });

  it('selectFormattedRemainingTime floors fractional seconds', () => {
    const s = state({ queue: { tracks: [{ duration: 10 }, { duration: 200.5 }], currentIndex: 0 } });
    const out = selectFormattedRemainingTime(s);
    expect(out.total).toBe(200.5);
    expect(out.formatted).toBe('3m 20s');
  });

  it('keeps player selectors exported', () => {
    expect(typeof playerSelectors.selectCurrentTime).toBe('function');
  });
});
