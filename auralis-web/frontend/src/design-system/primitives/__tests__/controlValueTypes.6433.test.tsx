/**
 * Design-system controls report the value type the consumer declared (#6433).
 *
 * SegmentedControl was `value: string` / `onChange: (value: string) => void`, so every consumer
 * with a closed union cast the callback value and nothing tied its option list to the union.
 * Slider's MUI `onChange` reports `number | number[]`, so single-thumb consumers cast to number.
 * The `@ts-expect-error` lines are the assertion: `pnpm run type-check` fails if one compiles.
 */

import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@/test/test-utils';
import { SegmentedControl } from '../SegmentedControl';
import { Slider } from '../Slider';

type Sort = 'az' | 'year';
const SORT_OPTIONS: readonly { value: Sort; label: string }[] = [
  { value: 'az', label: 'A-Z' },
  { value: 'year', label: 'Year' },
];

describe('SegmentedControl<T>', () => {
  it('hands onChange the consumer\'s union without a cast', () => {
    const received: Sort[] = [];
    const onChange = (value: Sort) => received.push(value);
    render(<SegmentedControl value="az" onChange={onChange} options={SORT_OPTIONS} />);

    fireEvent.click(screen.getByText('Year'));

    expect(received).toEqual(['year']);
  });

  it('rejects an option or value outside the union at compile time', () => {
    const onChange = vi.fn((_value: Sort) => {});
    render(
      <>
        <SegmentedControl
          value="az"
          onChange={onChange}
          // @ts-expect-error -- 'era' is not in Sort
          options={[{ value: 'era', label: 'Era' }]}
        />
        {/* @ts-expect-error -- 'era' is not a Sort value */}
        <SegmentedControl value="era" onChange={onChange} options={SORT_OPTIONS} />
      </>
    );
    expect(screen.getAllByRole('group')).toHaveLength(2);
  });
});

describe('Slider onValueChange', () => {
  it('reports a plain number for a single thumb', () => {
    const onValueChange = vi.fn();
    render(<Slider value={0.5} min={0} max={1} step={0.1} onValueChange={onValueChange} />);

    fireEvent.change(screen.getByRole('slider'), { target: { value: '0.7' } });

    expect(onValueChange).toHaveBeenCalledWith(0.7);
  });

  it('is not called for a range slider, and the raw onChange still fires', () => {
    const onValueChange = vi.fn();
    const onChange = vi.fn();
    render(<Slider value={[0.2, 0.8]} min={0} max={1} step={0.1} onChange={onChange} onValueChange={onValueChange} />);

    fireEvent.change(screen.getAllByRole('slider')[0], { target: { value: '0.3' } });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onValueChange).not.toHaveBeenCalled();
  });
});
