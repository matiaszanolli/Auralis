/**
 * AppTopBarSearchInput — clear button accessibility (#4449)
 *
 * The clear IconButton (shown whenever the query is non-empty) previously
 * rendered only <CloseIcon /> with no aria-label. It now has an accessible
 * name, and only appears when there is a query to clear.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { AppTopBarSearchInput } from '../AppTopBarSearchInput';

function renderInput(overrides: Partial<Parameters<typeof AppTopBarSearchInput>[0]> = {}) {
  const props = {
    searchQuery: 'daft punk',
    isSearchFocused: false,
    minWidth: 200,
    onSearchChange: vi.fn(),
    onFocus: vi.fn(),
    onBlur: vi.fn(),
    onClear: vi.fn(),
    ...overrides,
  };
  render(<AppTopBarSearchInput {...props} />);
  return props;
}

describe('AppTopBarSearchInput clear button (#4449)', () => {
  it('exposes an accessible name on the clear button when a query is present', () => {
    renderInput();

    expect(
      screen.getByRole('button', { name: /clear search/i })
    ).toBeInTheDocument();
  });

  it('invokes onClear when the clear button is activated', async () => {
    const user = userEvent.setup();
    const props = renderInput();

    await user.click(screen.getByRole('button', { name: /clear search/i }));

    expect(props.onClear).toHaveBeenCalledTimes(1);
  });

  it('does not render the clear button when the query is empty', () => {
    renderInput({ searchQuery: '' });

    expect(
      screen.queryByRole('button', { name: /clear search/i })
    ).not.toBeInTheDocument();
  });
});
