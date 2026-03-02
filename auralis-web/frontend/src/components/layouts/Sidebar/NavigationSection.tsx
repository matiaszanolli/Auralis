import React from 'react';
import { ListItem, ListItemIcon, ListItemText } from '@mui/material';
import { List, tokens } from '@/design-system';
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
                color: selectedItem === item.id ? tokens.colors.accent.primary : tokens.colors.text.tertiary, // Changed from secondary to tertiary
                minWidth: `calc(${tokens.spacing.lg} + ${tokens.spacing.sm})`, // 36px
                transition: tokens.transitions.color,
                opacity: selectedItem === item.id ? 1 : 0.7, // Fade inactive icons by ~30%
              }}
            >
              {item.icon}
            </ListItemIcon>
            <ListItemText
              primary={item.label}
              primaryTypographyProps={{
                fontSize: tokens.typography.fontSize.base,
                fontWeight: selectedItem === item.id ? tokens.typography.fontWeight.medium : tokens.typography.fontWeight.normal, // Reduced from semibold
                color: selectedItem === item.id ? tokens.colors.text.primary : tokens.colors.text.tertiary, // Changed from secondary to tertiary
                sx: { opacity: selectedItem === item.id ? 1 : 0.75 }, // Fade inactive text by ~25%
              }}
            />
          </StyledListItemButton>
        </ListItem>
      ))}
    </List>
  );
};

export default NavigationSection;
