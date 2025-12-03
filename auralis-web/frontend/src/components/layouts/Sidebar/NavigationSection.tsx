import React from 'react';
import { List, ListItem, ListItemIcon, ListItemText } from '@mui/material';
import { tokens } from '@/design-system';
import { StyledListItemButton } from './SidebarStyles';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
}

interface NavigationSectionProps {
  items: NavItem[];
  selectedItem: string;
  onItemClick: (itemId: string) => void;
}

/**
 * NavigationSection - Reusable navigation section with items
 *
 * Used for Library and Collections sections
 */
export const NavigationSection: React.FC<NavigationSectionProps> = ({
  items,
  selectedItem,
  onItemClick,
}) => {
  return (
    <List sx={{ px: tokens.spacing.md }}>
      {items.map((item) => (
        <ListItem key={item.id} disablePadding>
          <StyledListItemButton
            isactive={selectedItem === item.id ? 'true' : 'false'}
            onClick={() => onItemClick(item.id)}
          >
            <ListItemIcon
              sx={{
                color: selectedItem === item.id ? tokens.colors.accent.primary : tokens.colors.text.secondary,
                minWidth: `calc(${tokens.spacing.lg} + ${tokens.spacing.sm})`, // 36px
                transition: tokens.transitions.color,
              }}
            >
              {item.icon}
            </ListItemIcon>
            <ListItemText
              primary={item.label}
              primaryTypographyProps={{
                fontSize: tokens.typography.fontSize.base,
                fontWeight: selectedItem === item.id ? tokens.typography.fontWeight.semibold : tokens.typography.fontWeight.normal,
                color: selectedItem === item.id ? tokens.colors.text.primary : tokens.colors.text.secondary,
              }}
            />
          </StyledListItemButton>
        </ListItem>
      ))}
    </List>
  );
};

export default NavigationSection;
