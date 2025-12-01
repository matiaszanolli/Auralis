/**
 * ProgressBar Component Tests
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import ProgressBar from '@/components/player/ProgressBar';
import { usePlaybackPosition } from '@/hooks/player/usePlaybackState';
import { useSeekControl } from '@/hooks/player/usePlaybackControl';

vi.mock('@/hooks/player/usePlaybackState');
vi.mock('@/hooks/player/usePlaybackControl');

describe('ProgressBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render time display with current position and duration', () => {
    vi.mocked(usePlaybackPosition).mockReturnValue({
      position: 120,
      duration: 300,
    });

    vi.mocked(useSeekControl).mockReturnValue({
      seek: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<ProgressBar />);

    expect(screen.getByText(/2:00/)).toBeInTheDocument();
    expect(screen.getByText(/5:00/)).toBeInTheDocument();
  });

  it('should render a slider input', () => {
    vi.mocked(usePlaybackPosition).mockReturnValue({
      position: 0,
      duration: 300,
    });

    vi.mocked(useSeekControl).mockReturnValue({
      seek: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<ProgressBar />);

    const slider = screen.getByRole('slider');
    expect(slider).toBeInTheDocument();
  });

  it('should update position display when user drags slider', async () => {
    const mockSeek = vi.fn().mockResolvedValue(undefined);

    vi.mocked(usePlaybackPosition).mockReturnValue({
      position: 120,
      duration: 300,
    });

    vi.mocked(useSeekControl).mockReturnValue({
      seek: mockSeek,
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<ProgressBar />);

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '180' } });

    expect(mockSeek).toHaveBeenCalled();
  });

  it('should disable slider when duration is 0', () => {
    vi.mocked(usePlaybackPosition).mockReturnValue({
      position: 0,
      duration: 0,
    });

    vi.mocked(useSeekControl).mockReturnValue({
      seek: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<ProgressBar />);

    const slider = screen.getByRole('slider');
    expect(slider).toBeDisabled();
  });
});
