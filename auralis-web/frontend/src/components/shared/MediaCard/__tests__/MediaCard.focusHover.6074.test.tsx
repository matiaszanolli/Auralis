/**
 * MediaCard runs its hover callbacks on focus too (#6074)
 *
 * The Albums view fills its character pane from onHoverEnter/onHoverLeave, which MediaCard bound
 * only to mouseenter/mouseleave, so keyboard and touch users never saw it (WCAG 2.1.1).
 */

import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/test/test-utils';
import MediaCard from '../MediaCard';

const renderCard = () => {
  const onHoverEnter = vi.fn();
  const onHoverLeave = vi.fn();
  render(
    <>
      <MediaCard
        variant="album"
        id={7}
        title="Oktubre"
        artist="Patricio Rey"
        trackCount={8}
        duration={2400}
        onClick={vi.fn()}
        onHoverEnter={onHoverEnter}
        onHoverLeave={onHoverLeave}
      />
      <button type="button">elsewhere</button>
    </>,
  );
  return { onHoverEnter, onHoverLeave };
};

describe('MediaCard focus -> hover callbacks (#6074)', () => {
  it('focusing the card enters, tabbing within it does not leave, tabbing out leaves', async () => {
    const user = userEvent.setup();
    const { onHoverEnter, onHoverLeave } = renderCard();

    await user.tab(); // the stretched "open" button
    expect(onHoverEnter).toHaveBeenCalledWith(7);

    await user.tab(); // the play control, still inside the card
    expect(onHoverLeave).not.toHaveBeenCalled();

    await user.tab(); // out to the other button
    expect(screen.getByRole('button', { name: 'elsewhere' })).toHaveFocus();
    expect(onHoverLeave).toHaveBeenCalledTimes(1);
  });

  it('works without the callbacks', async () => {
    const user = userEvent.setup();
    render(
      <MediaCard variant="album" id={1} title="T" artist="A" trackCount={1} duration={60} onClick={vi.fn()} />,
    );

    await user.tab();
    await user.tab();
    await user.tab();

    expect(document.body).toBeInTheDocument();
  });
});
