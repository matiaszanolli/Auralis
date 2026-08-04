import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { MediaCardOverlay } from '../MediaCardOverlay';

describe('MediaCardOverlay visibility', () => {
  it('reveals the play control when it receives keyboard focus', () => {
    render(
      <MediaCardOverlay
        isHovered={false}
        onPlay={vi.fn()}
        title="Kind of Blue"
      />
    );

    const overlay = screen.getByTestId('media-card-play-overlay');
    const playButton = screen.getByRole('button', { name: 'Play Kind of Blue' });

    expect(overlay).toHaveStyle({ opacity: '0' });

    fireEvent.focus(playButton);
    expect(overlay).toHaveStyle({ opacity: '1' });

    fireEvent.blur(playButton);
    expect(overlay).toHaveStyle({ opacity: '0' });
  });

  it('remains visible while hovered or playing', () => {
    const { rerender } = render(
      <MediaCardOverlay isHovered onPlay={vi.fn()} title="Album" />
    );
    const overlay = screen.getByTestId('media-card-play-overlay');

    expect(overlay).toHaveStyle({ opacity: '1' });

    rerender(
      <MediaCardOverlay
        isHovered={false}
        isPlaying
        onPlay={vi.fn()}
        title="Album"
      />
    );
    expect(overlay).toHaveStyle({ opacity: '1' });
  });
});
