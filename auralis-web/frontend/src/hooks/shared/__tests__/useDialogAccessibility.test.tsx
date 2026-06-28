/**
 * useDialogAccessibility Tests
 *
 * Covers:
 * - Focus moves to first focusable element on mount
 * - Tab key wraps focus forward within the dialog (focus trap)
 * - Shift+Tab key wraps focus backward within the dialog
 * - Escape key calls the onClose callback
 * - Escape works even when the dialog has no focusable elements (regression: #2661)
 * - Focus is restored to the previously focused element on unmount
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { useDialogAccessibility } from '../useDialogAccessibility';

// ---------------------------------------------------------------------------
// Test components
// ---------------------------------------------------------------------------

function TestDialog({ onClose }: { onClose: () => void }) {
  const dialogRef = useDialogAccessibility(onClose);
  return (
    <div ref={dialogRef} role="dialog" aria-label="Test dialog">
      <button data-testid="btn-first">First</button>
      <button data-testid="btn-second">Second</button>
      <button data-testid="btn-last">Last</button>
    </div>
  );
}

function EmptyDialog({ onClose }: { onClose: () => void }) {
  const dialogRef = useDialogAccessibility(onClose);
  return <div ref={dialogRef} role="dialog" aria-label="Empty dialog" />;
}

function TestApp({ showDialog, onClose }: { showDialog: boolean; onClose: () => void }) {
  return (
    <div>
      <button data-testid="outside-btn">Outside</button>
      {showDialog && <TestDialog onClose={onClose} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useDialogAccessibility', () => {
  let onClose: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onClose = vi.fn();
  });

  // -------------------------------------------------------------------------
  // Mount behaviour
  // -------------------------------------------------------------------------

  describe('focus management on mount', () => {
    it('moves focus to the first focusable element when the dialog opens', () => {
      render(<TestDialog onClose={onClose} />);

      expect(document.activeElement).toBe(screen.getByTestId('btn-first'));
    });
  });

  // -------------------------------------------------------------------------
  // Focus trap
  // -------------------------------------------------------------------------

  describe('focus trap', () => {
    it('wraps focus from last element to first on Tab', () => {
      render(<TestDialog onClose={onClose} />);

      const lastBtn = screen.getByTestId('btn-last');
      lastBtn.focus();
      expect(document.activeElement).toBe(lastBtn);

      fireEvent.keyDown(lastBtn, { key: 'Tab', shiftKey: false });

      expect(document.activeElement).toBe(screen.getByTestId('btn-first'));
    });

    it('wraps focus from first element to last on Shift+Tab', () => {
      render(<TestDialog onClose={onClose} />);

      const firstBtn = screen.getByTestId('btn-first');
      firstBtn.focus();
      expect(document.activeElement).toBe(firstBtn);

      fireEvent.keyDown(firstBtn, { key: 'Tab', shiftKey: true });

      expect(document.activeElement).toBe(screen.getByTestId('btn-last'));
    });

    it('does not force-jump focus for Tab on a mid-list element', () => {
      render(<TestDialog onClose={onClose} />);

      const secondBtn = screen.getByTestId('btn-second');
      secondBtn.focus();

      // The handler only acts at the boundary (first/last); mid-list Tab is
      // left to the browser — in jsdom it won't naturally move focus either.
      fireEvent.keyDown(secondBtn, { key: 'Tab', shiftKey: false });

      expect(document.activeElement).toBe(secondBtn);
    });
  });

  // -------------------------------------------------------------------------
  // Escape key
  // -------------------------------------------------------------------------

  describe('Escape key', () => {
    it('calls onClose when Escape is pressed inside the dialog', () => {
      render(<TestDialog onClose={onClose} />);

      fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when Escape is pressed on a focused child element', () => {
      render(<TestDialog onClose={onClose} />);

      // The keydown event bubbles up to the container listener
      fireEvent.keyDown(screen.getByTestId('btn-first'), { key: 'Escape' });

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose even when the dialog contains no focusable elements (regression: #2661)', () => {
      render(<EmptyDialog onClose={onClose} />);

      fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not call onClose for other keys', () => {
      render(<TestDialog onClose={onClose} />);

      fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Enter' });
      fireEvent.keyDown(screen.getByRole('dialog'), { key: 'ArrowDown' });

      expect(onClose).not.toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  // Focus restoration on unmount
  // -------------------------------------------------------------------------

  describe('focus restoration on unmount', () => {
    it('restores focus to the previously focused element when the dialog closes', () => {
      const { rerender } = render(<TestApp showDialog={false} onClose={onClose} />);

      const outsideBtn = screen.getByTestId('outside-btn');
      outsideBtn.focus();
      expect(document.activeElement).toBe(outsideBtn);

      // Mount the dialog — saveFocus records outsideBtn, focus moves inside
      rerender(<TestApp showDialog={true} onClose={onClose} />);
      expect(document.activeElement).toBe(screen.getByTestId('btn-first'));

      // Unmount the dialog — restoreFocus returns focus to outsideBtn
      rerender(<TestApp showDialog={false} onClose={onClose} />);
      expect(document.activeElement).toBe(outsideBtn);
    });
  });

  // -------------------------------------------------------------------------
  // isActive toggle for stays-mounted dialogs (#4148)
  // -------------------------------------------------------------------------

  describe('isActive toggle (stays-mounted dialog, e.g. QueueSearchPanel)', () => {
    // Mirrors QueueSearchPanel: the component stays mounted and toggles the
    // dialog body via `return null`, so the trap must (re)create on isActive.
    function ToggleDialog({ isOpen, onClose: oc }: { isOpen: boolean; onClose: () => void }) {
      const dialogRef = useDialogAccessibility(oc, isOpen);
      if (!isOpen) return null;
      return (
        <div ref={dialogRef} role="dialog" aria-label="Toggle dialog">
          <button data-testid="btn-first">First</button>
          <button data-testid="btn-last">Last</button>
        </div>
      );
    }
    function ToggleApp({ isOpen, onClose: oc }: { isOpen: boolean; onClose: () => void }) {
      return (
        <div>
          <button data-testid="trigger">Trigger</button>
          <ToggleDialog isOpen={isOpen} onClose={oc} />
        </div>
      );
    }

    it('creates the trap when isActive flips true and traps Tab', () => {
      const { rerender } = render(<ToggleApp isOpen={false} onClose={onClose} />);
      const trigger = screen.getByTestId('trigger');
      trigger.focus();
      expect(document.activeElement).toBe(trigger);

      // Open: effect re-runs (isActive dep), trap created, focus moves inside.
      rerender(<ToggleApp isOpen={true} onClose={onClose} />);
      expect(document.activeElement).toBe(screen.getByTestId('btn-first'));

      // Tab from last wraps to first (focus stays inside the dialog).
      const lastBtn = screen.getByTestId('btn-last');
      lastBtn.focus();
      fireEvent.keyDown(lastBtn, { key: 'Tab', shiftKey: false });
      expect(document.activeElement).toBe(screen.getByTestId('btn-first'));
    });

    it('restores focus to the trigger when isActive flips false', () => {
      const { rerender } = render(<ToggleApp isOpen={false} onClose={onClose} />);
      const trigger = screen.getByTestId('trigger');
      trigger.focus();

      rerender(<ToggleApp isOpen={true} onClose={onClose} />);
      expect(document.activeElement).toBe(screen.getByTestId('btn-first'));

      // Close: cleanup runs, focus restored to the opener.
      rerender(<ToggleApp isOpen={false} onClose={onClose} />);
      expect(document.activeElement).toBe(trigger);
    });

    it('does not trap or forward Escape while isActive is false', () => {
      render(<ToggleApp isOpen={false} onClose={onClose} />);
      // No dialog rendered, so nothing to assert on it; Escape on the document
      // body must not invoke onClose (no trap installed).
      fireEvent.keyDown(document.body, { key: 'Escape' });
      expect(onClose).not.toHaveBeenCalled();
    });
  });
});
