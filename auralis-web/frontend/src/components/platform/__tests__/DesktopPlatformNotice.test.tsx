import { beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@/test/test-utils';
import DesktopPlatformNotice from '../DesktopPlatformNotice';

describe('DesktopPlatformNotice', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'electronAPI', {
      configurable: true,
      writable: true,
      value: undefined,
    });
  });

  it('marks standalone browser execution as unsupported', () => {
    render(<DesktopPlatformNotice />);

    expect(screen.getByRole('status', { name: 'Platform support notice' })).toHaveTextContent(
      'Browser preview — unsupported platform'
    );
  });

  it('does not render inside the supported Electron application', () => {
    Object.defineProperty(window, 'electronAPI', {
      configurable: true,
      writable: true,
      value: {
        selectFolder: async () => null,
      } satisfies ElectronAPI,
    });

    render(<DesktopPlatformNotice />);

    expect(screen.queryByRole('status', { name: 'Platform support notice' })).not.toBeInTheDocument();
  });
});
