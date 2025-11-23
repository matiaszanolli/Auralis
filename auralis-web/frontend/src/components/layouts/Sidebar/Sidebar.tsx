import React from 'react';
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
const SidebarComponent: React.FC<SidebarProps> = ({
  collapsed = false,
  onToggleCollapse,
  onNavigate,
  onOpenSettings,
}) => {
  const { selectedItem, handleItemClick } = useSidebarState(onNavigate);

  // Show collapsed variant
  if (collapsed) {
    return <CollapsedSidebar onToggleCollapse={onToggleCollapse} />;
  }

  return (
    <SidebarContainer>
      <SidebarHeader onToggleCollapse={onToggleCollapse} />
      <SidebarContent selectedItem={selectedItem} onItemClick={handleItemClick} />
      <SidebarFooter onOpenSettings={onOpenSettings} />
    </SidebarContainer>
  );
};

// Memoize for performance
const Sidebar = React.memo(SidebarComponent);

export default Sidebar;
