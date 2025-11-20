/**
 * Virtual Scrolling Integration Tests
 *
 * Tests for virtual scrolling performance and large list rendering.
 *
 * Test Categories:
 * 1. Virtual Scrolling (5 tests)
 *
 * Previously part of performance-large-libraries.test.tsx (lines 509-646)
 */

import { describe, it, expect } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/test/test-utils';
import * as React from 'react';

// Virtual scrolling component mock
const VirtualList = ({
  items,
  itemHeight = 50,
  visibleCount = 10
}: {
  items: any[],
  itemHeight?: number,
  visibleCount?: number
}) => {
  const [scrollTop, setScrollTop] = React.useState(0);
  const containerRef = React.useRef<HTMLDivElement>(null);

  // Calculate visible range
  const startIndex = Math.floor(scrollTop / itemHeight);
  const endIndex = Math.min(startIndex + visibleCount, items.length);
  const visibleItems = items.slice(startIndex, endIndex);

  // Calculate offset for positioning
  const offsetY = startIndex * itemHeight;
  const totalHeight = items.length * itemHeight;

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  };

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      data-testid="virtual-list"
      style={{ height: `${visibleCount * itemHeight}px`, overflow: 'auto' }}
    >
      <div style={{ height: `${totalHeight}px`, position: 'relative' }}>
        <div style={{ position: 'absolute', top: `${offsetY}px`, width: '100%' }}>
          {visibleItems.map((item, idx) => (
            <div
              key={startIndex + idx}
              data-testid={`virtual-item-${startIndex + idx}`}
              style={{ height: `${itemHeight}px` }}
            >
              {item.title}
            </div>
          ))}
        </div>
      </div>
      <div data-testid="visible-count">{visibleItems.length}</div>
      <div data-testid="total-count">{items.length}</div>
    </div>
  );
};

describe('Virtual Scrolling Integration Tests', () => {
  it('should render only visible items', () => {
    // Arrange
    const items = Array.from({ length: 1000 }, (_, i) => ({
      id: i + 1,
      title: `Item ${i + 1}`
    }));

    // Act
    render(<VirtualList items={items} itemHeight={50} visibleCount={10} />);

    // Assert - Should only render ~10 visible items, not all 1000
    const visibleCount = screen.getByTestId('visible-count');
    expect(visibleCount).toHaveTextContent('10');

    const totalCount = screen.getByTestId('total-count');
    expect(totalCount).toHaveTextContent('1000');
  });

  it('should update DOM when scrolling', async () => {
    // Arrange
    const items = Array.from({ length: 100 }, (_, i) => ({
      id: i + 1,
      title: `Item ${i + 1}`
    }));

    // Act
    render(<VirtualList items={items} itemHeight={50} visibleCount={10} />);

    // Initial state
    expect(screen.getByTestId('virtual-item-0')).toBeInTheDocument();
    expect(screen.queryByTestId('virtual-item-20')).not.toBeInTheDocument();

    // Simulate scroll
    const virtualList = screen.getByTestId('virtual-list');
    virtualList.scrollTop = 1000; // Scroll down
    virtualList.dispatchEvent(new Event('scroll'));

    // Assert - Should show different items after scroll
    await waitFor(() => {
      // After scrolling, item-0 should be out of view
      expect(screen.queryByTestId('virtual-item-0')).not.toBeInTheDocument();
    });
  });

  it('should maintain scroll position on data updates', async () => {
    // Arrange
    const InitialItems = Array.from({ length: 100 }, (_, i) => ({
      id: i + 1,
      title: `Item ${i + 1}`
    }));

    const VirtualListWrapper = () => {
      const [items, setItems] = React.useState(InitialItems);

      return (
        <div>
          <button
            onClick={() => setItems([...items, { id: 101, title: 'Item 101' }])}
            data-testid="add-item"
          >
            Add Item
          </button>
          <VirtualList items={items} itemHeight={50} visibleCount={10} />
        </div>
      );
    };

    // Act
    render(<VirtualListWrapper />);

    // Scroll to position
    const virtualList = screen.getByTestId('virtual-list');
    virtualList.scrollTop = 500;
    virtualList.dispatchEvent(new Event('scroll'));

    await waitFor(() => {
      expect(screen.getByTestId('virtual-list')).toHaveProperty('scrollTop', 500);
    });

    const scrollPositionBefore = virtualList.scrollTop;

    // Update data
    const addBtn = screen.getByTestId('add-item');
    await userEvent.click(addBtn);

    // Assert - Scroll position should be maintained
    await waitFor(() => {
      const scrollPositionAfter = virtualList.scrollTop;
      expect(scrollPositionAfter).toBe(scrollPositionBefore);
    });
  });

  it('should handle rapid scroll events without lag', async () => {
    // Arrange
    const items = Array.from({ length: 1000 }, (_, i) => ({
      id: i + 1,
      title: `Item ${i + 1}`
    }));

    // Act
    render(<VirtualList items={items} itemHeight={50} visibleCount={10} />);

    const virtualList = screen.getByTestId('virtual-list');
    const scrollEvents = 20;
    const startTime = performance.now();

    // Simulate rapid scrolling
    for (let i = 0; i < scrollEvents; i++) {
      virtualList.scrollTop = i * 100;
      virtualList.dispatchEvent(new Event('scroll'));
    }

    const endTime = performance.now();
    const totalTime = endTime - startTime;
    const avgTimePerScroll = totalTime / scrollEvents;

    // Assert - Each scroll should process quickly (< 16.6ms for 60fps)
    expect(avgTimePerScroll).toBeLessThan(16.6);
  });

  it('should be memory efficient with large lists', () => {
    // Arrange
    const items = Array.from({ length: 10000 }, (_, i) => ({
      id: i + 1,
      title: `Item ${i + 1}`
    }));

    // Act
    const { container } = render(
      <VirtualList items={items} itemHeight={50} visibleCount={10} />
    );

    // Assert - Should only have ~10 DOM nodes, not 10,000
    const renderedItems = container.querySelectorAll('[data-testid^="virtual-item-"]');
    expect(renderedItems.length).toBeLessThanOrEqual(15); // Allow some buffer
    expect(renderedItems.length).toBeGreaterThan(5);
  });
});
