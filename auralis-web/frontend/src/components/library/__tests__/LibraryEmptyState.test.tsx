/**
 * LibraryEmptyState Component Tests
 *
 * Tests the empty state router with:
 * - View-specific empty states (favorites, library, search)
 * - Conditional rendering based on context
 * - Callback propagation for actions
 * - Accessibility and semantic structure
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { LibraryEmptyState } from '../LibraryEmptyState';
import { auralisTheme } from '../../../theme/auralisTheme';

// Mock the shared EmptyState components
vi.mock('../../shared/EmptyState', () => ({
  EmptyLibrary: ({ onScanFolder, scanning }: any) => (
    <div data-testid="empty-library">
      <p>Library Empty</p>
      <button onClick={onScanFolder} data-testid="scan-button">
        Scan Folder
      </button>
      {scanning && <p>Scanning...</p>}
    </div>
  ),
  NoSearchResults: ({ query }: any) => (
    <div data-testid="no-search-results">
      <p>No results for "{query}"</p>
    </div>
  ),
  EmptyState: ({ icon, title, description }: any) => (
    <div data-testid="empty-state">
      <p>{title}</p>
      <p>{description}</p>
    </div>
  ),
}));

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('LibraryEmptyState', () => {
  describe('View-Based Rendering', () => {
    it('should render library empty state when no search query and view is library', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('empty-library')).toBeInTheDocument();
    });

    it('should render favorites empty state when view is favourites', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="favourites"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText(/No favorites yet/)).toBeInTheDocument();
    });

    it('should render search results empty state when search query is present', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery="nonexistent"
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('no-search-results')).toBeInTheDocument();
      expect(screen.getByText(/No results for "nonexistent"/)).toBeInTheDocument();
    });
  });

  describe('Favorites View', () => {
    it('should display favorites empty state title', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="favourites"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByText(/No favorites yet/)).toBeInTheDocument();
    });

    it('should display favorites help text', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="favourites"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(
        screen.getByText(/Click the heart icon on tracks you love/i)
      ).toBeInTheDocument();
    });

    it('should ignore search query when view is favourites', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="favourites"
            searchQuery="test query"
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      // Should still show favorites empty state, not search results
      expect(screen.getByText(/No favorites yet/)).toBeInTheDocument();
      expect(screen.queryByTestId('no-search-results')).not.toBeInTheDocument();
    });
  });

  describe('Search Results View', () => {
    it('should display search query in empty results message', () => {
      const mockScanFolder = jest.fn();
      const searchQuery = 'rare song title';
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery={searchQuery}
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByText(`No results for "${searchQuery}"`)).toBeInTheDocument();
    });

    it('should prioritize search query over view type', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery="test"
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('no-search-results')).toBeInTheDocument();
    });

    it('should show library empty state when search query is empty string', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('empty-library')).toBeInTheDocument();
    });
  });

  describe('Library Empty State', () => {
    it('should display scan folder button', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      const scanButton = screen.getByTestId('scan-button');
      expect(scanButton).toBeInTheDocument();
    });

    it('should call onScanFolder when scan button clicked', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      const scanButton = screen.getByTestId('scan-button');
      scanButton.click();

      expect(mockScanFolder).toHaveBeenCalledTimes(1);
    });

    it('should show scanning state when scanning prop is true', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={true}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByText(/Scanning.../)).toBeInTheDocument();
    });

    it('should hide scanning state when scanning prop is false', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.queryByText(/Scanning.../)).not.toBeInTheDocument();
    });
  });

  describe('State Transitions', () => {
    it('should switch from library to favorites empty state on prop change', () => {
      const mockScanFolder = jest.fn();
      const { rerender } = render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('empty-library')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <LibraryEmptyState
            view="favourites"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText(/No favorites yet/)).toBeInTheDocument();
    });

    it('should switch from library to search results on search query change', () => {
      const mockScanFolder = jest.fn();
      const { rerender } = render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('empty-library')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery="test"
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('no-search-results')).toBeInTheDocument();
    });

    it('should show search results when search query is present in library view', () => {
      const mockScanFolder = jest.fn();
      const { rerender } = render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('empty-library')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery="search term"
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('no-search-results')).toBeInTheDocument();
    });
  });

  describe('Scanning State', () => {
    it('should toggle scanning indicator when scanning changes', () => {
      const mockScanFolder = jest.fn();
      const { rerender } = render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.queryByText(/Scanning.../)).not.toBeInTheDocument();

      rerender(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={true}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(screen.getByText(/Scanning.../)).toBeInTheDocument();
    });
  });

  describe('Callback Handling', () => {
    it('should accept onScanFolder callback', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      expect(mockScanFolder).not.toHaveBeenCalled();
    });

    it('should pass onScanFolder to EmptyLibrary component', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      const scanButton = screen.getByTestId('scan-button');
      scanButton.click();

      expect(mockScanFolder).toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty view string', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view=""
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      // Should fall back to library empty state
      expect(screen.getByTestId('empty-library')).toBeInTheDocument();
    });

    it('should handle unknown view type', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="unknown-view"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      // Should fall back to library empty state
      expect(screen.getByTestId('empty-library')).toBeInTheDocument();
    });

    it('should handle whitespace in search query as empty', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery="   "
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      // Whitespace is still truthy, so it should show search results
      expect(screen.getByTestId('no-search-results')).toBeInTheDocument();
    });

    it('should handle case-sensitive view prop', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="Favourites"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      // Should not match "Favourites" (case-sensitive)
      expect(screen.getByTestId('empty-library')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible button for scan action', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="library"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      const scanButton = screen.getByTestId('scan-button');
      expect(scanButton).toBeInTheDocument();
      expect(scanButton.tagName).toBe('BUTTON');
    });

    it('should display descriptive text for all empty states', () => {
      const mockScanFolder = jest.fn();
      render(
        <Wrapper>
          <LibraryEmptyState
            view="favourites"
            searchQuery=""
            scanning={false}
            onScanFolder={mockScanFolder}
          />
        </Wrapper>
      );

      const title = screen.getByText(/No favorites yet/);
      const description = screen.getByText(/Click the heart icon/);

      expect(title).toBeInTheDocument();
      expect(description).toBeInTheDocument();
    });
  });
});
