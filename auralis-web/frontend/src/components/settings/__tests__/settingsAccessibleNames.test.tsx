/**
 * Settings controls expose accessible names (#5666)
 *
 * Six Selects announced themselves by value alone ("combobox, 16-bit") and
 * two number inputs had only a sibling styled label. Every control now names
 * itself after its visible label.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { AudioSettingsPanel } from '../AudioSettingsPanel';
import { InterfaceSettingsPanel } from '../InterfaceSettingsPanel';
import { EnhancementSettingsPanel } from '../EnhancementSettingsPanel';
import { AutoScanSettings } from '../AutoScanSettings';
import { AdvancedSettingsPanel } from '../AdvancedSettingsPanel';

const onChange = vi.fn();

describe('settings accessible names (#5666)', () => {
  it('names the three audio Selects', () => {
    render(
      <AudioSettingsPanel
        outputDevice="default"
        bitDepth={16}
        sampleRate={44100}
        onSettingChange={onChange}
      />
    );

    expect(screen.getByRole('combobox', { name: 'Output Device' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Bit Depth' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Sample Rate' })).toBeInTheDocument();
  });

  it('names the Theme Select', () => {
    render(
      <InterfaceSettingsPanel
        theme="dark"
        showVisualizations
        miniPlayerOnClose={false}
        onSettingChange={onChange}
      />
    );

    expect(screen.getByRole('combobox', { name: 'Theme' })).toBeInTheDocument();
  });

  it('names the Default Preset Select', () => {
    render(
      <EnhancementSettingsPanel
        defaultPreset="adaptive"
        autoEnhance
        enhancementIntensity={0.7}
        onSettingChange={onChange}
      />
    );

    expect(screen.getByRole('combobox', { name: 'Default Preset' })).toBeInTheDocument();
  });

  it('names the Scan Interval Select', () => {
    render(<AutoScanSettings autoScan scanInterval={300} onSettingChange={onChange} />);

    expect(screen.getByRole('combobox', { name: 'Scan interval' })).toBeInTheDocument();
  });

  it('names the two number inputs', () => {
    render(
      <AdvancedSettingsPanel
        cacheSize={1024}
        maxConcurrentScans={4}
        enableAnalytics={false}
        debugMode={false}
        onSettingChange={onChange}
      />
    );

    expect(screen.getByRole('spinbutton', { name: 'Cache size (MB)' })).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', { name: 'Max concurrent scans' })).toBeInTheDocument();
  });

  it('uses unique DOM ids for the label references', () => {
    const { container } = render(
      <>
        <AudioSettingsPanel
          outputDevice="default"
          bitDepth={16}
          sampleRate={44100}
          onSettingChange={onChange}
        />
        <InterfaceSettingsPanel
          theme="dark"
          showVisualizations
          miniPlayerOnClose={false}
          onSettingChange={onChange}
        />
        <EnhancementSettingsPanel
          defaultPreset="adaptive"
          autoEnhance
          enhancementIntensity={0.7}
          onSettingChange={onChange}
        />
      </>
    );

    const ids = Array.from(container.querySelectorAll('[id]')).map((el) => el.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
