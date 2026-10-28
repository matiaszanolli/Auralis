/**
 * Collapsing or expanding the sidebar keeps keyboard focus on the toggle (#6070).
 *
 * The collapsed sidebar is a different component tree, so the focused button
 * unmounted and focus fell to <body>.
 */

import { useState } from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import Sidebar from '../Sidebar';

function Harness() {
  const [collapsed, setCollapsed] = useState(false);
  return <Sidebar collapsed={collapsed} onToggleCollapse={() => setCollapsed((c) => !c)} />;
}

describe('Sidebar collapse toggle focus (#6070)', () => {
  it('moves focus to the Expand button after collapsing, and back after expanding', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toHaveFocus();

    await user.click(screen.getByRole('button', { name: 'Expand sidebar' }));
    expect(screen.getByRole('button', { name: 'Collapse sidebar' })).toHaveFocus();
  });

  it('does not steal focus when the prop changes without a user toggle', () => {
    const { rerender } = render(<Sidebar collapsed={false} />);
    rerender(<Sidebar collapsed />);

    expect(screen.getByRole('button', { name: 'Expand sidebar' })).not.toHaveFocus();
  });
});
