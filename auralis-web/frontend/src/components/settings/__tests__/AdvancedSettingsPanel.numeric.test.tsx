/**
 * Numeric settings inputs never write NaN into pending changes (#5635)
 *
 * parseInt('') is NaN: a controlled TextField then renders React's
 * NaN-value warning and JSON.stringify serialises it as null in the PUT
 * body on Save, surfacing only as a generic "Failed to save settings".
 * A cleared field keeps the last valid value, and values clamp to the
 * range each input's min/max attributes advertise.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { AdvancedSettingsPanel } from '../AdvancedSettingsPanel';

const onChange = vi.fn();

const renderPanel = () =>
  render(
    <AdvancedSettingsPanel
      cacheSize={1024}
      maxConcurrentScans={4}
      enableAnalytics={false}
      debugMode={false}
      onSettingChange={onChange}
    />
  );

describe('numeric settings inputs (#5635)', () => {
  it('ignores a cleared cache-size field instead of storing NaN', async () => {
    const user = userEvent.setup();
    renderPanel();

    const field = screen.getByLabelText('Cache size (MB)');
    await user.clear(field);

    expect(onChange).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalledWith('cache_size', NaN);
  });

  it('ignores a cleared max-concurrent-scans field instead of storing NaN', async () => {
    const user = userEvent.setup();
    renderPanel();

    const field = screen.getByLabelText('Max concurrent scans');
    await user.clear(field);

    expect(onChange).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalledWith('max_concurrent_scans', NaN);
  });

  it('clamps to the advertised min/max instead of passing the raw value through', async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.clear(screen.getByLabelText('Cache size (MB)'));
    await user.type(screen.getByLabelText('Cache size (MB)'), '99999');
    expect(onChange).toHaveBeenLastCalledWith('cache_size', 8192);

    await user.clear(screen.getByLabelText('Cache size (MB)'));
    await user.type(screen.getByLabelText('Cache size (MB)'), '32');
    expect(onChange).toHaveBeenLastCalledWith('cache_size', 128);

    await user.clear(screen.getByLabelText('Max concurrent scans'));
    await user.type(screen.getByLabelText('Max concurrent scans'), '0');
    expect(onChange).toHaveBeenLastCalledWith('max_concurrent_scans', 1);

    await user.clear(screen.getByLabelText('Max concurrent scans'));
    await user.type(screen.getByLabelText('Max concurrent scans'), '64');
    expect(onChange).toHaveBeenLastCalledWith('max_concurrent_scans', 16);
  });

  it('still accepts a valid value unchanged', async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.clear(screen.getByLabelText('Cache size (MB)'));
    await user.type(screen.getByLabelText('Cache size (MB)'), '2048');
    expect(onChange).toHaveBeenLastCalledWith('cache_size', 2048);
  });
});
