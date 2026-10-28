/**
 * IconButton's accessible name comes from its tooltip when no aria-label is given
 * (#5134). The icon-only "Remove folder" button relied on exactly that; MUI's
 * Tooltip supplies aria-label from a string title, and this pins the contract so a
 * future Tooltip option (describeChild) or wrapper change cannot silently strip it.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import DeleteIcon from '@mui/icons-material/Delete';
import { IconButton } from '../IconButton';

describe('IconButton accessible name', () => {
  it('names an icon-only button from its tooltip', () => {
    render(<IconButton tooltip="Remove this folder"><DeleteIcon /></IconButton>);

    expect(screen.getByRole('button', { name: 'Remove this folder' })).toBeInTheDocument();
  });

  it('lets an explicit aria-label win over the tooltip', () => {
    render(
      <IconButton tooltip="Remove this folder" aria-label="Remove Music folder"><DeleteIcon /></IconButton>
    );

    expect(screen.getByRole('button', { name: 'Remove Music folder' })).toBeInTheDocument();
  });

  it('still names a disabled button, where the tooltip is not mounted', () => {
    render(<IconButton tooltip="Remove this folder" disabled><DeleteIcon /></IconButton>);

    expect(screen.getByRole('button', { name: 'Remove this folder' })).toBeDisabled();
  });

  it('adds no aria-label when there is neither a tooltip nor an explicit label', () => {
    render(<IconButton data-testid="bare"><DeleteIcon /></IconButton>);

    expect(screen.getByTestId('bare')).not.toHaveAttribute('aria-label');
  });
});
