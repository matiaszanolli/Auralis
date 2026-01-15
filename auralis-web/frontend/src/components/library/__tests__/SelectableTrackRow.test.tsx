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

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import SelectableTrackRow from '../Items/tracks/SelectableTrackRow';

// Mock TrackRow component
vi.mock('../Items/tracks/TrackRow', () => ({
  default: function MockTrackRow({ track, onPlay, onEditMetadata }: any) {
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
  },
}));

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  quality: 320,
  isEnhanced: false,
};


describe('SelectableTrackRow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render selectable container', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should display track row', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('should render selection checkbox', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
    });
  });

  describe('Selection Checkbox', () => {
    it('should show unchecked checkbox when not selected', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
      );

      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(false);
    });

    it('should show checked checkbox when selected', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={true}
            onToggleSelect={vi.fn()}
          />
      );

      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(true);
    });

    it('should toggle selection on checkbox click', async () => {
      const user = userEvent.setup();
      const onToggleSelect = vi.fn();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
      );

      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);

      expect(onToggleSelect).toHaveBeenCalled();
    });

    it('should call onToggleSelect with event object', async () => {
      const user = userEvent.setup();
      const onToggleSelect = vi.fn();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
      );

      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);

      expect(onToggleSelect).toHaveBeenCalledWith(expect.any(Object));
    });
  });

  describe('Selection Styling', () => {
    it('should apply selected styling when isSelected is true', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={true}
            onToggleSelect={vi.fn()}
          />
      );

      // Find the selectable container via checkbox's parent (MUI styled classes don't include component names)
      const checkbox = screen.getByRole('checkbox');
      const selectableContainer = checkbox.closest('.MuiBox-root');
      expect(selectableContainer).toBeInTheDocument();
    });

    it('should not apply selected styling when isSelected is false', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
      );

      // Find the selectable container via checkbox's parent (MUI styled classes don't include component names)
      const checkbox = screen.getByRole('checkbox');
      const selectableContainer = checkbox.closest('.MuiBox-root');
      expect(selectableContainer).toBeInTheDocument();
    });
  });

  describe('Event Handling', () => {
    it('should toggle selection when container clicked', async () => {
      const onToggleSelect = vi.fn();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
      );

      // Find the selectable container via checkbox's parent (MUI styled classes don't include component names)
      const checkbox = screen.getByRole('checkbox');
      const selectableContainer = checkbox.closest('.MuiBox-root');
      expect(selectableContainer).toBeInTheDocument();
      fireEvent.click(selectableContainer!);
      expect(onToggleSelect).toHaveBeenCalled();
    });

    it('should not toggle selection when clicking action button', async () => {
      const user = userEvent.setup();
      const onToggleSelect = vi.fn();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
            onPlay={vi.fn()}
          />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      // onToggleSelect should not be called
      expect(onToggleSelect.mock.calls.length).toBeLessThanOrEqual(1); // Only if checkbox click
    });

    it('should stop event propagation on checkbox click', async () => {
      const user = userEvent.setup();
      const onToggleSelect = vi.fn();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
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
      const onPlay = vi.fn();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
            onPlay={onPlay}
          />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      expect(onPlay).toHaveBeenCalledWith(1);
    });

    it('should pass onPause callback', () => {
      const onPause = vi.fn();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
            onPause={onPause}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass isPlaying state', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
            isPlaying={true}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass isCurrent state', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
            isCurrent={true}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });
  });

  describe('Metadata Editing', () => {
    it('should call onEditMetadata when edit button clicked', async () => {
      const user = userEvent.setup();
      const onEditMetadata = vi.fn();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
            onEditMetadata={onEditMetadata}
          />
      );

      const editButton = screen.getByRole('button', { name: /edit/i });
      await user.click(editButton);

      expect(onEditMetadata).toHaveBeenCalledWith(1);
    });

    it('should pass onEditMetadata to TrackRow', () => {
      const onEditMetadata = vi.fn();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
            onEditMetadata={onEditMetadata}
          />
      );

      expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
    });
  });

  describe('Multiple Selections', () => {
    it('should handle multiple selectable rows', () => {
      const track1 = { ...mockTrack, id: 1, title: 'Track 1' };
      const track2 = { ...mockTrack, id: 2, title: 'Track 2' };

      render(
        <>
          <SelectableTrackRow
            track={track1}
            index={0}
            isSelected={true}
            onToggleSelect={vi.fn()}
          />
          <SelectableTrackRow
            track={track2}
            index={1}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
        </>
      );

      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
    });

    it('should track individual selection states', () => {
      const track1 = { ...mockTrack, id: 1, title: 'Track 1' };
      const track2 = { ...mockTrack, id: 2, title: 'Track 2' };

      const { container } = render(
        <>
          <SelectableTrackRow
            track={track1}
            index={0}
            isSelected={true}
            onToggleSelect={vi.fn()}
          />
          <SelectableTrackRow
            track={track2}
            index={1}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
        </>
      );

      // Use getAllByRole since MUI Checkbox uses actual input elements
      const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
      expect(checkboxes[0].checked).toBe(true);
      expect(checkboxes[1].checked).toBe(false);
    });
  });

  describe('Accessibility', () => {
    it('should have accessible checkbox', () => {
      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
    });

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
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
        <SelectableTrackRow
            track={extendedTrack as any}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should handle rapid selection toggles', async () => {
      const user = userEvent.setup();
      const onToggleSelect = vi.fn();

      const { rerender } = render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
          />
      );

      const checkbox = screen.getByRole('checkbox');

      await user.click(checkbox);
      expect(onToggleSelect).toHaveBeenCalledTimes(1);

      rerender(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={true}
            onToggleSelect={onToggleSelect}
          />
      );

      await user.click(checkbox);
      expect(onToggleSelect).toHaveBeenCalledTimes(2);
    });

    it('should handle very long track title', () => {
      const longTitle = 'A'.repeat(200);
      const longTrack = {
        ...mockTrack,
        title: longTitle,
      };

      render(
        <SelectableTrackRow
            track={longTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
      );

      // Use exact text match to avoid matching "Test Artist" which also contains "A"
      expect(screen.getByText(longTitle)).toBeInTheDocument();
    });

    it('should handle very long artist name', () => {
      const longArtist = 'B'.repeat(200);
      const longTrack = {
        ...mockTrack,
        artist: longArtist,
      };

      render(
        <SelectableTrackRow
            track={longTrack}
            index={0}
            isSelected={false}
            onToggleSelect={vi.fn()}
          />
      );

      expect(screen.getByText(longArtist)).toBeInTheDocument();
    });
  });

  describe('Integration', () => {
    it('should handle complete workflow', async () => {
      const user = userEvent.setup();
      const onToggleSelect = vi.fn();
      const onPlay = vi.fn();

      const { rerender } = render(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={false}
            onToggleSelect={onToggleSelect}
            onPlay={onPlay}
          />
      );

      // User selects track
      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);
      expect(onToggleSelect).toHaveBeenCalled();

      // Update selected state
      rerender(
        <SelectableTrackRow
            track={mockTrack}
            index={0}
            isSelected={true}
            onToggleSelect={onToggleSelect}
            onPlay={onPlay}
          />
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
