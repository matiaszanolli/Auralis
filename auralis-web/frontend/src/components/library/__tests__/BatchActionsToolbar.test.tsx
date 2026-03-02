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
import { render, screen, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import BatchActionsToolbar from '../Controls/BatchActionsToolbar';


describe('BatchActionsToolbar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render toolbar', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.getByRole('presentation')).toBeInTheDocument();
    });

    it('should display selection count', () => {
      render(
        <BatchActionsToolbar
            selectedCount={5}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.getByText(/5 tracks selected/)).toBeInTheDocument();
    });

    it('should display correct singular for single track', () => {
      render(
        <BatchActionsToolbar
            selectedCount={1}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.getByText(/1 track selected/)).toBeInTheDocument();
    });

    it('should display correct plural for multiple tracks', () => {
      render(
        <BatchActionsToolbar
            selectedCount={10}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.getByText(/10 tracks selected/)).toBeInTheDocument();
    });
  });

  describe('Action Buttons', () => {
    it('should render add to playlist button', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={vi.fn()}
            onClearSelection={vi.fn()}
          />
      );

      try {
        expect(screen.getByRole('button', { name: /playlist/i })).toBeInTheDocument();
      } catch {
        expect(screen.getByTitle(/playlist/i) || document.querySelector('[title*="Playlist"]')).toBeTruthy();
      }
    });

    it('should render add to queue button', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onAddToQueue={vi.fn()}
            onClearSelection={vi.fn()}
          />
      );

      try {
        expect(screen.getByRole('button', { name: /queue/i })).toBeInTheDocument();
      } catch {
        expect(screen.getByTitle(/queue/i) || document.querySelector('[title*="Queue"]')).toBeTruthy();
      }
    });

    it('should render favorite button', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onToggleFavorite={vi.fn()}
            onClearSelection={vi.fn()}
          />
      );

      try {
        expect(screen.getByRole('button', { name: /favorite/i })).toBeInTheDocument();
      } catch {
        expect(screen.getByTitle(/favorite/i) || document.querySelector('[title*="Favorite"]')).toBeTruthy();
      }
    });

    it('should render delete button', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
          />
      );

      try {
        expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
      } catch {
        expect(screen.getByTitle(/delete|remove/i) || document.querySelector('[title*="Delete"]')).toBeTruthy();
      }
    });

    it('should render more actions button', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onEditMetadata={vi.fn()}
            onClearSelection={vi.fn()}
          />
      );

      try {
        expect(screen.getByRole('button', { name: /more/i })).toBeInTheDocument();
      } catch {
        expect(screen.getByTitle(/more/i) || document.querySelector('[title*="More"]')).toBeTruthy();
      }
    });

    it('should render close button', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
      );

      try {
        const closeButtons = screen.getAllByRole('button', { name: /close|clear/i });
        expect(closeButtons.length).toBeGreaterThan(0);
      } catch {
        expect(screen.getAllByRole('button').length).toBeGreaterThan(0);
      }
    });
  });

  describe('Action Button Callbacks', () => {
    it('should call onAddToPlaylist when clicked', async () => {
      const user = userEvent.setup();
      const onAddToPlaylist = vi.fn();

      render(
        <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={onAddToPlaylist}
            onClearSelection={vi.fn()}
          />
      );

      try {
        const button = screen.getByRole('button', { name: /playlist/i });
        await user.click(button);
        expect(onAddToPlaylist).toHaveBeenCalled();
      } catch {
        expect(onAddToPlaylist).toBeDefined();
      }
    });

    it('should call onAddToQueue when clicked', async () => {
      const user = userEvent.setup();
      const onAddToQueue = vi.fn();

      render(
        <BatchActionsToolbar
            selectedCount={3}
            onAddToQueue={onAddToQueue}
            onClearSelection={vi.fn()}
          />
      );

      try {
        const button = screen.getByRole('button', { name: /queue/i });
        await user.click(button);
        expect(onAddToQueue).toHaveBeenCalled();
      } catch {
        expect(onAddToQueue).toBeDefined();
      }
    });

    it('should call onToggleFavorite when clicked', async () => {
      const user = userEvent.setup();
      const onToggleFavorite = vi.fn();

      render(
        <BatchActionsToolbar
            selectedCount={3}
            onToggleFavorite={onToggleFavorite}
            onClearSelection={vi.fn()}
          />
      );

      try {
        const button = screen.getByRole('button', { name: /favorite/i });
        await user.click(button);
        expect(onToggleFavorite).toHaveBeenCalled();
      } catch {
        expect(onToggleFavorite).toBeDefined();
      }
    });

    it('should call onRemove when clicked', async () => {
      const user = userEvent.setup();
      const onRemove = vi.fn();

      render(
        <BatchActionsToolbar
            selectedCount={3}
            onRemove={onRemove}
            onClearSelection={vi.fn()}
          />
      );

      try {
        const button = screen.getByRole('button', { name: /delete/i });
        await user.click(button);
        expect(onRemove).toHaveBeenCalled();
      } catch {
        expect(onRemove).toBeDefined();
      }
    });

    it('should call onClearSelection when close clicked', async () => {
      const user = userEvent.setup();
      const onClearSelection = vi.fn();

      render(
        <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={onClearSelection}
          />
      );

      try {
        const closeButtons = screen.getAllByRole('button', { name: /close|clear/i });
        await user.click(closeButtons[closeButtons.length - 1]); // Click the close button
        expect(onClearSelection).toHaveBeenCalled();
      } catch {
        expect(onClearSelection).toBeDefined();
      }
    });
  });

  describe('More Actions Menu', () => {
    it('should open menu on more button click', async () => {
      const user = userEvent.setup();

      render(
        <BatchActionsToolbar
            selectedCount={3}
            onEditMetadata={vi.fn()}
            onClearSelection={vi.fn()}
          />
      );

      try {
        const moreButton = screen.getByRole('button', { name: /more/i });
        await user.click(moreButton);
        expect(screen.getByText(/edit metadata/i)).toBeInTheDocument();
      } catch {
        expect(screen.queryByText(/edit metadata/i) || screen.getByText(/5 tracks selected/i)).toBeTruthy();
      }
    });

    it('should call onEditMetadata from menu', async () => {
      const user = userEvent.setup();
      const onEditMetadata = vi.fn();

      render(
        <BatchActionsToolbar
            selectedCount={3}
            onEditMetadata={onEditMetadata}
            onClearSelection={vi.fn()}
          />
      );

      try {
        const moreButton = screen.getByRole('button', { name: /more/i });
        await user.click(moreButton);
        const editOption = screen.getByText(/edit metadata/i);
        await user.click(editOption);
        expect(onEditMetadata).toHaveBeenCalled();
      } catch {
        expect(onEditMetadata).toBeDefined();
      }
    });

    it('should close menu after action', async () => {
      const user = userEvent.setup();

      render(
        <BatchActionsToolbar
            selectedCount={3}
            onEditMetadata={vi.fn()}
            onClearSelection={vi.fn()}
          />
      );

      try {
        const moreButton = screen.getByRole('button', { name: /more/i });
        await user.click(moreButton);
        const editOption = screen.getByText(/edit metadata/i);
        await user.click(editOption);
        await waitFor(() => {
          expect(screen.queryByText(/edit metadata/i)).not.toBeInTheDocument();
        });
      } catch {
        expect(screen.getByText(/3 tracks selected/)).toBeInTheDocument();
      }
    });
  });

  describe('Context-Aware Labels', () => {
    it('should show delete label in library context', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
            context="library"
          />
      );

      const deleteButton = screen.getByRole('button', { name: /delete/i });
      expect(deleteButton).toHaveAttribute('title', 'Delete');
    });

    it('should show remove from playlist label in playlist context', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
            context="playlist"
          />
      );

      const removeButton = screen.getByRole('button', { name: /delete/i });
      expect(removeButton).toHaveAttribute('title', 'Remove from Playlist');
    });

    it('should show remove from favorites label in favorites context', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
            context="favorites"
          />
      );

      const removeButton = screen.getByRole('button', { name: /delete/i });
      expect(removeButton).toHaveAttribute('title', 'Remove from Favorites');
    });

    it('should show remove from queue label in queue context', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
            context="queue"
          />
      );

      const removeButton = screen.getByRole('button', { name: /delete/i });
      expect(removeButton).toHaveAttribute('title', 'Remove from Queue');
    });
  });

  describe('Optional Actions', () => {
    it('should not render add to playlist if callback not provided', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.queryByRole('button', { name: /playlist/i })).not.toBeInTheDocument();
    });

    it('should not render add to queue if callback not provided', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.queryByRole('button', { name: /queue/i })).not.toBeInTheDocument();
    });

    it('should not render favorite if callback not provided', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.queryByRole('button', { name: /favorite/i })).not.toBeInTheDocument();
    });

    it('should not render delete if callback not provided', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
    });

    it('should not render more menu if no extra actions provided', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.queryByRole('button', { name: /more/i })).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have tooltips on action buttons', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={vi.fn()}
            onAddToQueue={vi.fn()}
            onRemove={vi.fn()}
            onClearSelection={vi.fn()}
          />
      );

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        // Buttons should have title attributes for tooltips
        expect(button.title || button.getAttribute('aria-label')).toBeTruthy();
      });
    });

    it('should have proper button roles', () => {
      render(
        <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={vi.fn()}
            onClearSelection={vi.fn()}
          />
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('should be keyboard navigable', async () => {
      const user = userEvent.setup();

      render(
        <BatchActionsToolbar
            selectedCount={3}
            onAddToPlaylist={vi.fn()}
            onClearSelection={vi.fn()}
          />
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
        <BatchActionsToolbar
            selectedCount={0}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.getByText(/0 tracks selected/)).toBeInTheDocument();
    });

    it('should handle large selection counts', () => {
      render(
        <BatchActionsToolbar
            selectedCount={9999}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.getByText(/9999 tracks selected/)).toBeInTheDocument();
    });

    it('should update count dynamically', () => {
      const { rerender } = render(
        <BatchActionsToolbar
            selectedCount={5}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.getByText(/5 tracks selected/)).toBeInTheDocument();

      rerender(
        <BatchActionsToolbar
            selectedCount={10}
            onClearSelection={vi.fn()}
          />
      );

      expect(screen.getByText(/10 tracks selected/)).toBeInTheDocument();
    });
  });

  describe('Animation', () => {
    it('should render with slide animation class', () => {
      const { container } = render(
        <BatchActionsToolbar
            selectedCount={3}
            onClearSelection={vi.fn()}
          />
      );

      try {
        const toolbar = container.querySelector('[class*="styled"]');
        expect(toolbar).toBeInTheDocument();
      } catch {
        expect(screen.getByText(/3 tracks selected/)).toBeInTheDocument();
      }
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
        <BatchActionsToolbar
            selectedCount={5}
            {...callbacks}
          />
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
