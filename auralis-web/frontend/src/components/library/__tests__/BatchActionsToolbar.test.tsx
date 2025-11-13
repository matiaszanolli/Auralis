/**
 * BatchActionsToolbar Component Tests
 *
 * Tests the batch actions toolbar for multi-track operations:
 * - Selection count display
 * - Action buttons (add to playlist, queue, delete, favorite)
 * - Context-aware labels
 * - More actions menu
 * - Clear selection
 * - Animation on mount/unmount
 */

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import BatchActionsToolbar from '../BatchActionsToolbar';
import { auralisTheme } from '../../../theme/auralisTheme';

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('BatchActionsToolbar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render toolbar', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByRole('presentation')).toBeInTheDocument();
    });

    it('should display selection count', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={5}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText(/5 tracks selected/)).toBeInTheDocument();
    });

    it('should display correct singular for single track', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={1}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText(/1 track selected/)).toBeInTheDocument();
    });

    it('should display correct plural for multiple tracks', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={10}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText(/10 tracks selected/)).toBeInTheDocument();
    });
  });

  describe('Action Buttons', () => {
    it('should render add to playlist button', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByRole('button', { name: /playlist/i })).toBeInTheDocument();
    });

    it('should render add to queue button', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onAddToQueue={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByRole('button', { name: /queue/i })).toBeInTheDocument();
    });

    it('should render favorite button', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onToggleFavorite={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByRole('button', { name: /favorite/i })).toBeInTheDocument();
    });

    it('should render delete button', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
    });

    it('should render more actions button', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onEditMetadata={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByRole('button', { name: /more/i })).toBeInTheDocument();
    });

    it('should render close button', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const closeButtons = screen.getAllByRole('button', { name: /close|clear/i });
      expect(closeButtons.length).toBeGreaterThan(0);
    });
  });

  describe('Action Button Callbacks', () => {
    it('should call onAddToPlaylist when clicked', async () => {
      const user = userEvent.setup();
      const onAddToPlaylist = vi.fn();

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={onAddToPlaylist}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const button = screen.getByRole('button', { name: /playlist/i });
      await user.click(button);

      expect(onAddToPlaylist).toHaveBeenCalled();
    });

    it('should call onAddToQueue when clicked', async () => {
      const user = userEvent.setup();
      const onAddToQueue = vi.fn();

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onAddToQueue={onAddToQueue}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const button = screen.getByRole('button', { name: /queue/i });
      await user.click(button);

      expect(onAddToQueue).toHaveBeenCalled();
    });

    it('should call onToggleFavorite when clicked', async () => {
      const user = userEvent.setup();
      const onToggleFavorite = vi.fn();

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onToggleFavorite={onToggleFavorite}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const button = screen.getByRole('button', { name: /favorite/i });
      await user.click(button);

      expect(onToggleFavorite).toHaveBeenCalled();
    });

    it('should call onRemove when clicked', async () => {
      const user = userEvent.setup();
      const onRemove = vi.fn();

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onRemove={onRemove}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const button = screen.getByRole('button', { name: /delete/i });
      await user.click(button);

      expect(onRemove).toHaveBeenCalled();
    });

    it('should call onClearSelection when close clicked', async () => {
      const user = userEvent.setup();
      const onClearSelection = vi.fn();

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={onClearSelection}
          />
        </Wrapper>
      );

      const closeButtons = screen.getAllByRole('button', { name: /close|clear/i });
      await user.click(closeButtons[closeButtons.length - 1]); // Click the close button

      expect(onClearSelection).toHaveBeenCalled();
    });
  });

  describe('More Actions Menu', () => {
    it('should open menu on more button click', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onEditMetadata={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const moreButton = screen.getByRole('button', { name: /more/i });
      await user.click(moreButton);

      expect(screen.getByText(/edit metadata/i)).toBeInTheDocument();
    });

    it('should call onEditMetadata from menu', async () => {
      const user = userEvent.setup();
      const onEditMetadata = vi.fn();

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onEditMetadata={onEditMetadata}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const moreButton = screen.getByRole('button', { name: /more/i });
      await user.click(moreButton);

      const editOption = screen.getByText(/edit metadata/i);
      await user.click(editOption);

      expect(onEditMetadata).toHaveBeenCalled();
    });

    it('should close menu after action', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onEditMetadata={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const moreButton = screen.getByRole('button', { name: /more/i });
      await user.click(moreButton);

      const editOption = screen.getByText(/edit metadata/i);
      await user.click(editOption);

      await waitFor(() => {
        expect(screen.queryByText(/edit metadata/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Context-Aware Labels', () => {
    it('should show delete label in library context', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
            context="library"
          />
        </Wrapper>
      );

      const deleteButton = screen.getByRole('button', { name: /delete/i });
      expect(deleteButton).toHaveAttribute('title', 'Delete');
    });

    it('should show remove from playlist label in playlist context', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
            context="playlist"
          />
        </Wrapper>
      );

      const removeButton = screen.getByRole('button', { name: /delete/i });
      expect(removeButton).toHaveAttribute('title', 'Remove from Playlist');
    });

    it('should show remove from favorites label in favorites context', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
            context="favorites"
          />
        </Wrapper>
      );

      const removeButton = screen.getByRole('button', { name: /delete/i });
      expect(removeButton).toHaveAttribute('title', 'Remove from Favorites');
    });

    it('should show remove from queue label in queue context', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
            context="queue"
          />
        </Wrapper>
      );

      const removeButton = screen.getByRole('button', { name: /delete/i });
      expect(removeButton).toHaveAttribute('title', 'Remove from Queue');
    });
  });

  describe('Optional Actions', () => {
    it('should not render add to playlist if callback not provided', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.queryByRole('button', { name: /playlist/i })).not.toBeInTheDocument();
    });

    it('should not render add to queue if callback not provided', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.queryByRole('button', { name: /queue/i })).not.toBeInTheDocument();
    });

    it('should not render favorite if callback not provided', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.queryByRole('button', { name: /favorite/i })).not.toBeInTheDocument();
    });

    it('should not render delete if callback not provided', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
    });

    it('should not render more menu if no extra actions provided', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.queryByRole('button', { name: /more/i })).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have tooltips on action buttons', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={vi.fn()}
            onAddToQueue={vi.fn()}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        // Buttons should have title attributes for tooltips
        expect(button.title || button.getAttribute('aria-label')).toBeTruthy();
      });
    });

    it('should have proper button roles', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('should be keyboard navigable', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={vi.fn()}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const firstButton = screen.getAllByRole('button')[0];
      firstButton.focus();
      expect(document.activeElement).toBe(firstButton);

      await user.keyboard('{Enter}');
      expect(document.activeElement).toBeInTheDocument();
    });
  });

  describe('Selection Count Variations', () => {
    it('should handle zero selected tracks', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={0}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText(/0 tracks selected/)).toBeInTheDocument();
    });

    it('should handle large selection counts', () => {
      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={9999}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText(/9999 tracks selected/)).toBeInTheDocument();
    });

    it('should update count dynamically', () => {
      const { rerender } = render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={5}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText(/5 tracks selected/)).toBeInTheDocument();

      rerender(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={10}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText(/10 tracks selected/)).toBeInTheDocument();
    });
  });

  describe('Animation', () => {
    it('should render with slide animation class', () => {
      const { container } = render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
        </Wrapper>
      );

      const toolbar = container.querySelector('[class*="styled"]');
      expect(toolbar).toBeInTheDocument();
    });
  });

  describe('Integration', () => {
    it('should handle complete workflow', async () => {
      const user = userEvent.setup();
      const callbacks = {
        onAddToPlaylist: vi.fn(),
        onAddToQueue: vi.fn(),
        onToggleFavorite: vi.fn(),
        onRemove: vi.fn(),
        onEditMetadata: vi.fn(),
        onClearSelection: vi.fn(),
      };

      render(
        <Wrapper>
          <BatchActionsToolbar
            selectedCount={5}
            {...callbacks}
          />
        </Wrapper>
      );

      // Verify count
      expect(screen.getByText(/5 tracks selected/)).toBeInTheDocument();

      // Click add to playlist
      await user.click(screen.getByRole('button', { name: /playlist/i }));
      expect(callbacks.onAddToPlaylist).toHaveBeenCalled();

      // Click favorite
      await user.click(screen.getByRole('button', { name: /favorite/i }));
      expect(callbacks.onToggleFavorite).toHaveBeenCalled();

      // Open more menu
      await user.click(screen.getByRole('button', { name: /more/i }));
      await user.click(screen.getByText(/edit metadata/i));
      expect(callbacks.onEditMetadata).toHaveBeenCalled();

      // Clear selection
      const closeButtons = screen.getAllByRole('button', { name: /close|clear/i });
      await user.click(closeButtons[closeButtons.length - 1]);
      expect(callbacks.onClearSelection).toHaveBeenCalled();
    });
  });
});
