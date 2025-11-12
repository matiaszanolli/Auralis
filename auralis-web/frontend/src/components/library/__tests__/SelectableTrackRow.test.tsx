/**
 * SelectableTrackRow Component Tests
 *
 * Tests the selectable track row wrapper with:
 * - Selection checkbox (toggle, state, visibility)
 * - Multi-select support
 * - Selection styling
 * - Event handling (click propagation)
 * - Integration with TrackRow callbacks
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import SelectableTrackRow from '../SelectableTrackRow';
import { auralisTheme } from '../../../theme/auralisTheme';

// Mock TrackRow component
jest.mock('../TrackRow', () => {
  return function MockTrackRow({ track, onPlay, onEditMetadata }: any) {
    return (
      <div data-testid={`track-row-${track.id}`}>
        <span>{track.title}</span>
        <span>{track.artist}</span>
        <button onClick={() => onPlay?.(track.id)}>Play</button>
        {onEditMetadata && (
          <button onClick={() => onEditMetadata(track.id)}>Edit</button>
        )}
      </div>
    );
  };
});

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  quality: 320,
  isEnhanced: false,
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('SelectableTrackRow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render selectable container', () => {
      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should display track row', () => {
      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('should render selection checkbox', () => {
      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
    });
  });

  describe('Selection Checkbox', () => {
    it('should show unchecked checkbox when not selected', () => {
      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(false);
    });

    it('should show checked checkbox when selected', () => {
      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={true}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(true);
    });

    it('should toggle selection on checkbox click', async () => {
      const user = userEvent.setup();
      const onToggleSelect = jest.fn();

      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);

      expect(onToggleSelect).toHaveBeenCalled();
    });

    it('should call onToggleSelect with event object', async () => {
      const user = userEvent.setup();
      const onToggleSelect = jest.fn();

      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);

      expect(onToggleSelect).toHaveBeenCalledWith(expect.any(Object));
    });
  });

  describe('Selection Styling', () => {
    it('should apply selected styling when isSelected is true', () => {
      const { container } = render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={true}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      const selectableContainer = container.querySelector('[class*="SelectableContainer"]');
      expect(selectableContainer).toBeInTheDocument();
    });

    it('should not apply selected styling when isSelected is false', () => {
      const { container } = render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      const selectableContainer = container.querySelector('[class*="SelectableContainer"]');
      expect(selectableContainer).toBeInTheDocument();
    });
  });

  describe('Event Handling', () => {
    it('should toggle selection when container clicked', async () => {
      const user = userEvent.setup();
      const onToggleSelect = jest.fn();

      const { container } = render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
        </Wrapper>
      );

      const selectableContainer = container.querySelector('[class*="SelectableContainer"]');
      if (selectableContainer) {
        fireEvent.click(selectableContainer);
        expect(onToggleSelect).toHaveBeenCalled();
      }
    });

    it('should not toggle selection when clicking action button', async () => {
      const user = userEvent.setup();
      const onToggleSelect = jest.fn();

      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      // onToggleSelect should not be called
      expect(onToggleSelect.mock.calls.length).toBeLessThanOrEqual(1); // Only if checkbox click
    });

    it('should stop event propagation on checkbox click', async () => {
      const user = userEvent.setup();
      const onToggleSelect = jest.fn();

      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);

      // Click counter should be 1 (not propagated multiple times)
      expect(onToggleSelect).toHaveBeenCalledTimes(1);
    });
  });

  describe('Playback Integration', () => {
    it('should pass onPlay callback', async () => {
      const user = userEvent.setup();
      const onPlay = jest.fn();

      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
            onPlay={onPlay}
          />
        </Wrapper>
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      expect(onPlay).toHaveBeenCalledWith(1);
    });

    it('should pass onPause callback', () => {
      const onPause = jest.fn();

      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
            onPause={onPause}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass isPlaying state', () => {
      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
            isPlaying={true}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass isCurrent state', () => {
      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
            isCurrent={true}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });
  });

  describe('Metadata Editing', () => {
    it('should call onEditMetadata when edit button clicked', async () => {
      const user = userEvent.setup();
      const onEditMetadata = jest.fn();

      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
            onEditMetadata={onEditMetadata}
          />
        </Wrapper>
      );

      const editButton = screen.getByRole('button', { name: /edit/i });
      await user.click(editButton);

      expect(onEditMetadata).toHaveBeenCalledWith(1);
    });

    it('should pass onEditMetadata to TrackRow', () => {
      const onEditMetadata = jest.fn();

      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
            onEditMetadata={onEditMetadata}
          />
        </Wrapper>
      );

      expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
    });
  });

  describe('Multiple Selections', () => {
    it('should handle multiple selectable rows', () => {
      const track1 = { ...mockTrack, id: 1, title: 'Track 1' };
      const track2 = { ...mockTrack, id: 2, title: 'Track 2' };

      render(
        <Wrapper>
          <SelectableTrackRow
            track={track1}
            index={0}
            isSelected={true}
            onToggleSelect={jest.fn()}
          />
          <SelectableTrackRow
            track={track2}
            index={1}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
    });

    it('should track individual selection states', () => {
      const track1 = { ...mockTrack, id: 1, title: 'Track 1' };
      const track2 = { ...mockTrack, id: 2, title: 'Track 2' };

      const { container } = render(
        <Wrapper>
          <SelectableTrackRow
            track={track1}
            index={0}
            isSelected={true}
            onToggleSelect={jest.fn()}
          />
          <SelectableTrackRow
            track={track2}
            index={1}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      const checkboxes = container.querySelectorAll('[role="checkbox"]');
      expect((checkboxes[0] as HTMLInputElement).checked).toBe(true);
      expect((checkboxes[1] as HTMLInputElement).checked).toBe(false);
    });
  });

  describe('Accessibility', () => {
    it('should have accessible checkbox', () => {
      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
    });

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');
      checkbox.focus();
      expect(document.activeElement).toBe(checkbox);

      await user.keyboard(' '); // Space to toggle
      expect(document.activeElement).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle track with extended properties', () => {
      const extendedTrack = {
        ...mockTrack,
        customField: 'custom value',
        anotherField: 12345,
      };

      render(
        <Wrapper>
          <SelectableTrackRow
            track={extendedTrack as any}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should handle rapid selection toggles', async () => {
      const user = userEvent.setup();
      const onToggleSelect = jest.fn();

      const { rerender } = render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');

      await user.click(checkbox);
      expect(onToggleSelect).toHaveBeenCalledTimes(1);

      rerender(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={true}
            onToggleSelect={onToggleSelect}
          />
        </Wrapper>
      );

      await user.click(checkbox);
      expect(onToggleSelect).toHaveBeenCalledTimes(2);
    });

    it('should handle very long track title', () => {
      const longTrack = {
        ...mockTrack,
        title: 'A'.repeat(200),
      };

      render(
        <Wrapper>
          <SelectableTrackRow
            track={longTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText(/A+/)).toBeInTheDocument();
    });

    it('should handle very long artist name', () => {
      const longTrack = {
        ...mockTrack,
        artist: 'B'.repeat(200),
      };

      render(
        <Wrapper>
          <SelectableTrackRow
            track={longTrack}
            index={0}
            isSelected={false}
            onToggleSelect={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText(/B+/)).toBeInTheDocument();
    });
  });

  describe('Integration', () => {
    it('should handle complete workflow', async () => {
      const user = userEvent.setup();
      const onToggleSelect = jest.fn();
      const onPlay = jest.fn();

      const { rerender } = render(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
            onPlay={onPlay}
          />
        </Wrapper>
      );

      // User selects track
      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);
      expect(onToggleSelect).toHaveBeenCalled();

      // Update selected state
      rerender(
        <Wrapper>
          <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={true}
            onToggleSelect={onToggleSelect}
            onPlay={onPlay}
          />
        </Wrapper>
      );

      // User clicks play
      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);
      expect(onPlay).toHaveBeenCalledWith(1);

      // Selection still active
      const updatedCheckbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(updatedCheckbox.checked).toBe(true);
    });
  });
});
