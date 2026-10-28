import { memo, useCallback, useEffect, useRef } from 'react';
import CollapsedSidebar from './CollapsedSidebar';
import SidebarHeader from './SidebarHeader';
import SidebarContent from './SidebarContent';
import SidebarFooter from './SidebarFooter';
import { SidebarContainer } from './SidebarStyles';
import { useSidebarState } from './useSidebarState';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: (view: string) => void;
  onOpenSettings?: () => void;
}

/**
 * Sidebar - Main navigation sidebar component
 *
 * Features:
 * - Collapsible sidebar with smooth transitions
 * - Library navigation (Songs, Albums, Artists)
 * - Collections (Favorites, Recently Played)
 * - Dynamic playlist list
 * - Theme toggle and settings
 * - Active item highlighting with aurora glow
 */
const SidebarComponent = ({
  collapsed = false,
  onToggleCollapse,
  onNavigate,
  onOpenSettings,
}: SidebarProps) => {
  const { selectedItem, handleItemClick } = useSidebarState(onNavigate);

  // Collapsing swaps this tree for CollapsedSidebar (and back), so the focused
  // toggle button unmounts and focus falls to <body>. After a toggle the user
  // made, hand focus to the counterpart button (#6070).
  const refocusToggle = useRef(false);
  const handleToggle = useCallback(() => {
    refocusToggle.current = true;
    onToggleCollapse?.();
  }, [onToggleCollapse]);
  useEffect(() => {
    if (!refocusToggle.current) return;
    refocusToggle.current = false;
    document.querySelector<HTMLElement>('[data-sidebar-toggle]')?.focus();
  }, [collapsed]);

  // Show collapsed variant
  if (collapsed) {
    return <CollapsedSidebar onToggleCollapse={handleToggle} />;
  }

  return (
    <SidebarContainer>
      <SidebarHeader onToggleCollapse={handleToggle} />
      <SidebarContent selectedItem={selectedItem} onItemClick={handleItemClick} />
      <SidebarFooter onOpenSettings={onOpenSettings} />
    </SidebarContainer>
  );
};

// Memoize for performance
const Sidebar = memo(SidebarComponent);

export default Sidebar;
