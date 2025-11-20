/**
 * Memory Management Integration Tests
 *
 * Tests for memory leak prevention and cleanup.
 *
 * Test Categories:
 * 1. Memory Management (2 tests)
 *
 * Previously part of performance-large-libraries.test.tsx (lines 1014-1112)
 */

import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import * as React from 'react';

describe('Memory Management Integration Tests', () => {
  it('should have no memory leaks on component unmount', async () => {
    // Arrange
    const eventListeners: Array<() => void> = [];

    const ComponentWithListeners = () => {
      React.useEffect(() => {
        const handler = () => console.log('event');
        window.addEventListener('resize', handler);
        eventListeners.push(handler);

        return () => {
          window.removeEventListener('resize', handler);
          const index = eventListeners.indexOf(handler);
          if (index > -1) {
            eventListeners.splice(index, 1);
          }
        };
      }, []);

      return <div data-testid="component">Component</div>;
    };

    // Act
    const { unmount } = render(<ComponentWithListeners />);

    expect(screen.getByTestId('component')).toBeInTheDocument();
    expect(eventListeners.length).toBe(1);

    // Unmount
    unmount();

    // Assert - Event listeners should be cleaned up
    expect(eventListeners.length).toBe(0);
  });

  it('should efficiently cleanup event listeners', () => {
    // Arrange
    let listenerCount = 0;
    let startingListenerCount = 0;

    const originalAddEventListener = window.addEventListener;
    const originalRemoveEventListener = window.removeEventListener;

    // Track listener changes relative to baseline
    window.addEventListener = vi.fn((...args: any[]) => {
      listenerCount++;
      return originalAddEventListener.apply(window, args as any);
    });

    window.removeEventListener = vi.fn((...args: any[]) => {
      listenerCount--;
      return originalRemoveEventListener.apply(window, args as any);
    });

    const ComponentWithCleanup = () => {
      React.useEffect(() => {
        const handlers = {
          resize: () => {},
          scroll: () => {},
          click: () => {},
        };

        window.addEventListener('resize', handlers.resize);
        window.addEventListener('scroll', handlers.scroll);
        window.addEventListener('click', handlers.click);

        return () => {
          window.removeEventListener('resize', handlers.resize);
          window.removeEventListener('scroll', handlers.scroll);
          window.removeEventListener('click', handlers.click);
        };
      }, []);

      return <div data-testid="component">Component</div>;
    };

    // Capture baseline (other test infrastructure listeners)
    startingListenerCount = listenerCount;

    // Act
    const { unmount } = render(<ComponentWithCleanup />);

    const listenersAfterMount = listenerCount;
    // Should have added at least 3 listeners
    expect(listenersAfterMount - startingListenerCount).toBeGreaterThanOrEqual(3);

    unmount();

    // Assert - Should clean up at least 3 listeners (back closer to baseline)
    // Note: Test environment may add extra listeners, so we verify cleanup happened
    const listenersAfterUnmount = listenerCount;
    const cleanedUpCount = listenersAfterMount - listenersAfterUnmount;
    expect(cleanedUpCount).toBeGreaterThanOrEqual(3);

    // Restore original functions
    window.addEventListener = originalAddEventListener;
    window.removeEventListener = originalRemoveEventListener;
  });
});
