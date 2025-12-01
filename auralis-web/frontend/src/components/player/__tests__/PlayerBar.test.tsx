/**
 * PlayerBar Component Tests
 */

import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import PlayerBar from '@/components/player/PlayerBar';

// Mock all child components
vi.mock('@/components/player/TrackInfo', () => ({
  default: () => <div data-testid="track-info">TrackInfo</div>,
}));
vi.mock('@/components/player/ProgressBar', () => ({
  default: () => <div data-testid="progress-bar">ProgressBar</div>,
}));
vi.mock('@/components/player/PlaybackControls', () => ({
  default: () => <div data-testid="playback-controls">PlaybackControls</div>,
}));
vi.mock('@/components/player/VolumeControl', () => ({
  default: () => <div data-testid="volume-control">VolumeControl</div>,
}));

describe('PlayerBar', () => {
  it('should render all player sub-components', () => {
    render(<PlayerBar />);

    expect(screen.getByTestId('track-info')).toBeInTheDocument();
    expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
    expect(screen.getByTestId('playback-controls')).toBeInTheDocument();
    expect(screen.getByTestId('volume-control')).toBeInTheDocument();
  });

  it('should render as a flex container', () => {
    const { container } = render(<PlayerBar />);
    const playerBar = container.firstChild;

    const styles = window.getComputedStyle(playerBar as Element);
    expect(styles.display).toBe('flex');
  });
});
