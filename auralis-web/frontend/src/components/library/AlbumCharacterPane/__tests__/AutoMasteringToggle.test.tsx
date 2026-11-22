/**
 * AutoMasteringToggle (#6570): a failed toggle is reported, not an unhandled rejection.
 */

import { afterEach, describe, it, expect, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@/test/test-utils';
import { AutoMasteringToggle } from '@/components/library/AlbumCharacterPane/AutoMasteringToggle';

const control = vi.hoisted(() => ({
  enabled: true,
  isLoading: false,
  setEnabled: vi.fn<(value: boolean) => Promise<void>>(),
}));
const toast = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn(), info: vi.fn() }));

vi.mock('@/hooks/enhancement/useEnhancementControl', () => ({
  useEnhancementControl: () => control,
}));
vi.mock('@/components/shared/Toast', () => ({
  useToast: () => toast,
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

afterEach(() => {
  vi.clearAllMocks();
  control.isLoading = false;
});

describe('AutoMasteringToggle (#6570)', () => {
  it('reports a failed toggle in a toast instead of rejecting unhandled', async () => {
    const unhandled = vi.fn();
    process.on('unhandledRejection', unhandled);
    control.setEnabled.mockRejectedValueOnce(new Error('Too many requests'));
    try {
      render(<AutoMasteringToggle />);
      await act(async () => {
        fireEvent.click(screen.getByRole('switch', { name: 'Auto-Mastering' }));
      });
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      expect(control.setEnabled).toHaveBeenCalledWith(false);
      expect(toast.error).toHaveBeenCalledWith('Could not turn auto-mastering off: Too many requests');
      expect(unhandled).not.toHaveBeenCalled();
    } finally {
      process.off('unhandledRejection', unhandled);
    }
  });

  it('disables the switch while the toggle request is in flight', () => {
    control.isLoading = true;
    render(<AutoMasteringToggle />);
    expect(screen.getByRole('switch', { name: 'Auto-Mastering' })).toBeDisabled();
  });
});
