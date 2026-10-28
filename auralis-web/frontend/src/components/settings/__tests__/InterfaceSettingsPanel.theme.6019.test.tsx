/**
 * The Settings theme select drives the live theme (#6019)
 *
 * It used to show and write a free string setting that nothing read, while the real mode lived in
 * ThemeContext and was changed only by the sidebar toggle.
 */

import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/test/test-utils';
import { InterfaceSettingsPanel } from '../InterfaceSettingsPanel';
import { useTheme } from '@/contexts/ThemeContext';

const ModeProbe = () => <output data-testid="mode">{useTheme().mode}</output>;

const renderPanel = (onSettingChange = vi.fn()) => {
  render(
    <>
      <InterfaceSettingsPanel showVisualizations miniPlayerOnClose={false} onSettingChange={onSettingChange} />
      <ModeProbe />
    </>,
  );
  return onSettingChange;
};

describe('InterfaceSettingsPanel theme select (#6019)', () => {
  it('shows the live mode', () => {
    renderPanel();

    expect(screen.getByRole('combobox', { name: 'Theme' })).toHaveTextContent('Dark');
  });

  it('switching to Light changes the live theme and records the setting', async () => {
    const user = userEvent.setup();
    const onSettingChange = renderPanel();

    await user.click(screen.getByRole('combobox', { name: 'Theme' }));
    await user.click(within(screen.getByRole('listbox')).getByText('Light'));

    expect(screen.getByTestId('mode')).toHaveTextContent('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(onSettingChange).toHaveBeenCalledWith('theme', 'light');
  });
});
