import { ReactNode } from 'react';
import { ListItem, ListItemIcon, ListItemText } from '@mui/material';
import { List, tokens } from '@/design-system';
import { StyledListItemButton } from './SidebarStyles';
import { themeVars } from '@/theme/semanticTheme';

interface NavItem {
  id: string;
  label: string;
  icon: ReactNode;
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
export const NavigationSection = ({
  items,
  selectedItem,
  onItemClick,
}: NavigationSectionProps) => {
  return (
    <List sx={{ px: tokens.spacing.md }}>
      {items.map((item) => (
        <ListItem key={item.id} disablePadding>
          <StyledListItemButton
            isactive={selectedItem === item.id ? 'true' : 'false'}
            aria-current={selectedItem === item.id ? 'page' : undefined}
            onClick={() => onItemClick(item.id)}
          >
            <ListItemIcon
              sx={{
                color: selectedItem === item.id ? themeVars.accent : themeVars.textMuted,
                minWidth: `calc(${tokens.spacing.lg} + ${tokens.spacing.sm})`, // 36px
                transition: tokens.transitions.color,
                opacity: selectedItem === item.id ? 1 : 0.85,
              }}
            >
              {item.icon}
            </ListItemIcon>
            <ListItemText
              primary={item.label}
              slotProps={{
                primary: {
                  sx: {
                    fontSize: tokens.typography.fontSize.base,
                    fontWeight: selectedItem === item.id ? tokens.typography.fontWeight.medium : tokens.typography.fontWeight.normal,
                    color: selectedItem === item.id ? themeVars.textPrimary : themeVars.textSecondary,
                  },
                },
              }}
            />
          </StyledListItemButton>
        </ListItem>
      ))}
    </List>
  );
};

export default NavigationSection;
