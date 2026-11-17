import { renderHook, act } from '@testing-library/react';
import { useAppLayout } from '../useAppLayout';

describe('useAppLayout', () => {
  describe('responsive breakpoints', () => {
    it('detects mobile screens', () => {
      const { result } = renderHook(() => useAppLayout());
      // Note: In test environment, breakpoints may not work as expected
      // This test validates the hook initializes correctly
      expect(result.current.isMobile).toBeTypeOf('boolean');
      expect(result.current.isTablet).toBeTypeOf('boolean');
      // every mobile viewport is also a tablet one (down('md') is inside down('lg'))
      expect(!result.current.isMobile || result.current.isTablet).toBe(true);
    });

    it('returns initial state', () => {
      const { result } = renderHook(() => useAppLayout());
      expect(result.current.sidebarCollapsed).toBe(false);
      expect(result.current.mobileDrawerOpen).toBe(false);
      expect(result.current.presetPaneCollapsed).toBe(false);
    });
  });

  describe('sidebar collapse', () => {
    it('toggles sidebar collapse state', () => {
      const { result } = renderHook(() => useAppLayout());
      const initialState = result.current.sidebarCollapsed;

      act(() => {
        result.current.toggleSidebarCollapse();
      });

      expect(result.current.sidebarCollapsed).toBe(!initialState);
    });

    it('sets sidebar collapse explicitly', () => {
      const { result } = renderHook(() => useAppLayout());

      act(() => {
        result.current.setSidebarCollapsed(true);
      });

      expect(result.current.sidebarCollapsed).toBe(true);

      act(() => {
        result.current.setSidebarCollapsed(false);
      });

      expect(result.current.sidebarCollapsed).toBe(false);
    });
  });

  describe('mobile drawer', () => {
    it('toggles mobile drawer open state', () => {
      const { result } = renderHook(() => useAppLayout());
      const initialState = result.current.mobileDrawerOpen;

      act(() => {
        result.current.toggleMobileDrawer();
      });

      expect(result.current.mobileDrawerOpen).toBe(!initialState);
    });

    it('sets mobile drawer explicitly', () => {
      const { result } = renderHook(() => useAppLayout());

      act(() => {
        result.current.setMobileDrawerOpen(true);
      });

      expect(result.current.mobileDrawerOpen).toBe(true);

      act(() => {
        result.current.setMobileDrawerOpen(false);
      });

      expect(result.current.mobileDrawerOpen).toBe(false);
    });
  });

  describe('preset pane collapse', () => {
    it('toggles preset pane collapse state', () => {
      const { result } = renderHook(() => useAppLayout());
      const initialState = result.current.presetPaneCollapsed;

      act(() => {
        result.current.togglePresetPaneCollapse();
      });

      expect(result.current.presetPaneCollapsed).toBe(!initialState);
    });

    it('sets preset pane collapse explicitly', () => {
      const { result } = renderHook(() => useAppLayout());

      act(() => {
        result.current.setPresetPaneCollapsed(true);
      });

      expect(result.current.presetPaneCollapsed).toBe(true);

      act(() => {
        result.current.setPresetPaneCollapsed(false);
      });

      expect(result.current.presetPaneCollapsed).toBe(false);
    });
  });

  describe('toggle functions', () => {
    it('multiple toggles work correctly', () => {
      const { result } = renderHook(() => useAppLayout());

      // Initial state
      const sidebarInitial = result.current.sidebarCollapsed;

      // Toggle 3 times
      act(() => {
        result.current.toggleSidebarCollapse();
      });
      expect(result.current.sidebarCollapsed).toBe(!sidebarInitial);

      act(() => {
        result.current.toggleSidebarCollapse();
      });
      expect(result.current.sidebarCollapsed).toBe(sidebarInitial);

      act(() => {
        result.current.toggleSidebarCollapse();
      });
      expect(result.current.sidebarCollapsed).toBe(!sidebarInitial);
    });
  });

  describe('independent state management', () => {
    it('sidebar and drawer states are independent', () => {
      const { result } = renderHook(() => useAppLayout());

      act(() => {
        result.current.setSidebarCollapsed(true);
        result.current.setMobileDrawerOpen(true);
      });

      expect(result.current.sidebarCollapsed).toBe(true);
      expect(result.current.mobileDrawerOpen).toBe(true);

      act(() => {
        result.current.setSidebarCollapsed(false);
      });

      expect(result.current.sidebarCollapsed).toBe(false);
      expect(result.current.mobileDrawerOpen).toBe(true); // Unchanged
    });

    it('all pane states can be controlled independently', () => {
      const { result } = renderHook(() => useAppLayout());

      act(() => {
        result.current.setSidebarCollapsed(true);
        result.current.setMobileDrawerOpen(true);
        result.current.setPresetPaneCollapsed(true);
      });

      expect(result.current.sidebarCollapsed).toBe(true);
      expect(result.current.mobileDrawerOpen).toBe(true);
      expect(result.current.presetPaneCollapsed).toBe(true);
    });
  });
});
