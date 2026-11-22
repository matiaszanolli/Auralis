/**
 * Queue row keys (#4428, extracted #6703): position-independent, duplicate-safe.
 */

import { describe, it, expect } from 'vitest';
import { queueRowKeys } from '@/components/player/QueuePanel/useQueueRowKeys';

describe('queueRowKeys', () => {
  it('keys unique tracks by id alone, so a reorder keeps every key', () => {
    expect(queueRowKeys([{ id: 1 }, { id: 2 }, { id: 3 }])).toEqual(['qt-1', 'qt-2', 'qt-3']);
    expect(queueRowKeys([{ id: 3 }, { id: 1 }, { id: 2 }])).toEqual(['qt-3', 'qt-1', 'qt-2']);
  });

  it('disambiguates a repeated track by occurrence, not index', () => {
    expect(queueRowKeys([{ id: 5 }, { id: 9 }, { id: 5 }, { id: 5 }])).toEqual([
      'qt-5',
      'qt-9',
      'qt-5#1',
      'qt-5#2',
    ]);
  });
});
