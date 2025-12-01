/**
 * VolumeControl Component Tests
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import VolumeControl from '@/components/player/VolumeControl';
import { useVolume } from '@/hooks/player/usePlaybackState';
import { useVolumeControl } from '@/hooks/player/usePlaybackControl';

vi.mock('@/hooks/player/usePlaybackState');
vi.mock('@/hooks/player/usePlaybackControl');

describe('VolumeControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render volume slider', () => {
    vi.mocked(useVolume).mockReturnValue(0.5);
    vi.mocked(useVolumeControl).mockReturnValue({
      setVolume: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<VolumeControl />);

    const slider = screen.getByRole('slider');
    expect(slider).toBeInTheDocument();
  });

  it('should render mute button', () => {
    vi.mocked(useVolume).mockReturnValue(0.5);
    vi.mocked(useVolumeControl).mockReturnValue({
      setVolume: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<VolumeControl />);

    expect(screen.getByRole('button', { name: /mute/i })).toBeInTheDocument();
  });

  it('should display volume percentage', () => {
    vi.mocked(useVolume).mockReturnValue(0.8);
    vi.mocked(useVolumeControl).mockReturnValue({
      setVolume: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<VolumeControl />);

    expect(screen.getByText(/80%/)).toBeInTheDocument();
  });

  it('should call setVolume when slider changes', async () => {
    const mockSetVolume = vi.fn().mockResolvedValue(undefined);

    vi.mocked(useVolume).mockReturnValue(0.5);
    vi.mocked(useVolumeControl).mockReturnValue({
      setVolume: mockSetVolume,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<VolumeControl />);

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '0.7' } });
    fireEvent.mouseUp(slider);

    await waitFor(() => {
      expect(mockSetVolume).toHaveBeenCalled();
    });
  });

  it('should toggle mute on button click', async () => {
    const mockSetVolume = vi.fn().mockResolvedValue(undefined);

    vi.mocked(useVolume).mockReturnValue(0.5);
    vi.mocked(useVolumeControl).mockReturnValue({
      setVolume: mockSetVolume,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<VolumeControl />);

    const muteButton = screen.getByRole('button', { name: /mute/i });
    fireEvent.click(muteButton);

    await waitFor(() => {
      expect(mockSetVolume).toHaveBeenCalled();
    });
  });

  it('should disable controls when isLoading is true', () => {
    vi.mocked(useVolume).mockReturnValue(0.5);
    vi.mocked(useVolumeControl).mockReturnValue({
      setVolume: vi.fn(),
      isLoading: true,
      error: null,
      clearError: vi.fn(),
    });

    render(<VolumeControl />);

    const slider = screen.getByRole('slider');
    const muteButton = screen.getByRole('button', { name: /mute/i });

    expect(slider).toBeDisabled();
    expect(muteButton).toBeDisabled();
  });
});
