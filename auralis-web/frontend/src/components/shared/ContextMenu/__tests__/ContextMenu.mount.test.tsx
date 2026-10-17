/**
 * ContextMenu mount cost (#5659)
 *
 * Every library row renders its own ContextMenu (~35 rows), so anything the
 * component mounts while closed is paid per row. The Create Playlist dialog
 * used to mount unconditionally whenever a trackId was present — a closed
 * dialog per row. A closed menu must mount nothing; the dialog appears only
 * from the menu's create flow, and survives the menu itself closing because
 * that flow closes the menu first.
 */

import { describe, it, expect, vi } from 'vitest';
import { useState } from 'react';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { ContextMenu } from '../ContextMenu';
import type { ContextMenuAction } from '../contextMenuActions';

vi.mock('@/components/shared/Toast', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/components/shared/Toast')>()),
  useToast: () => ({ success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

const actions: ContextMenuAction[] = [
  { id: 'play', label: 'Play now', onClick: vi.fn() },
];

const baseProps = {
  actions,
  anchorPosition: { top: 10, left: 10 },
  onClose: vi.fn(),
  trackId: 1,
  trackTitle: 'Track',
  playlists: [] as never[],
  onAddToPlaylist: vi.fn(),
  onCreatePlaylist: vi.fn(),
};

function MenuHost({ initialOpen = false }: { initialOpen?: boolean }) {
  const [open, setOpen] = useState(initialOpen);
  return (
    <>
      <button onClick={() => setOpen(true)}>open menu</button>
      <ContextMenu {...baseProps} open={open} onClose={() => setOpen(false)} />
    </>
  );
}

describe('ContextMenu mount cost (#5659)', () => {
  it('mounts nothing while closed', () => {
    render(<ContextMenu {...baseProps} open={false} />);

    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows no create dialog while the menu is open', () => {
    render(<ContextMenu {...baseProps} open />);

    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('keeps the create dialog mounted after the menu closes mid-flow', async () => {
    const user = userEvent.setup();
    render(<MenuHost />);

    await user.click(screen.getByText('open menu'));
    await user.click(screen.getByText('Create New Playlist'));

    // The flow closes the menu as it opens the dialog — the dialog is the
    // visible surface now and must not unmount with the menu.
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
