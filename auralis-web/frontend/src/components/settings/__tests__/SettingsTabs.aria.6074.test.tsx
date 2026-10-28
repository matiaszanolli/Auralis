/**
 * The Settings dialog's tabs are a real tab/tabpanel pair (#6074)
 *
 * StyledTabs had no accessible name, the Tabs no id/aria-controls, and the conditionally rendered
 * panels no role="tabpanel"/aria-labelledby, so a screen reader announced six buttons and a pile of
 * unrelated controls. The pattern now matches ArtistDetailTabs.
 */

import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { SettingsTabNav, SETTINGS_PANEL_ID, settingsTabId } from '../SettingsTabNav';
import { SettingsDialogContentComponent } from '../SettingsDialogContent';

describe('SettingsTabNav (#6074)', () => {
  it('is a named tablist of six tabs, each controlling the one panel', () => {
    render(<SettingsTabNav activeTab={0} onTabChange={vi.fn()} />);

    expect(screen.getByRole('tablist', { name: 'Settings sections' })).toBeInTheDocument();
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(6);
    tabs.forEach((tab, index) => {
      expect(tab).toHaveAttribute('id', settingsTabId(index));
      expect(tab).toHaveAttribute('aria-controls', SETTINGS_PANEL_ID);
    });
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
  });

  it('keeps the Library label and its scan indicator', () => {
    render(<SettingsTabNav activeTab={1} onTabChange={vi.fn()} isScanning />);

    expect(screen.getByRole('tab', { name: /Library/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Playback' })).toHaveAttribute('aria-selected', 'true');
  });
});

describe('SettingsDialogContent panel (#6074)', () => {
  const content = (activeTab: number) =>
    render(
      <SettingsDialogContentComponent
        activeTab={activeTab}
        getValue={() => null}
        onSettingChange={vi.fn()}
        onAddFolder={vi.fn()}
        onRemoveFolder={vi.fn()}
        onScanNow={vi.fn()}
      />,
    );

  it.each([0, 1, 3, 5])('the visible panel is labelled by tab %i', (activeTab) => {
    content(activeTab);

    const panel = screen.getByRole('tabpanel');
    expect(panel).toHaveAttribute('id', SETTINGS_PANEL_ID);
    expect(panel).toHaveAttribute('aria-labelledby', settingsTabId(activeTab));
  });
});
