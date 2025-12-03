/**
 * List Primitive Component
 *
 * Container for list items with consistent styling.
 *
 * Usage:
 *   <List>
 *     <ListItem>Item 1</ListItem>
 *     <ListItem>Item 2</ListItem>
 *   </List>
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import MuiList, { ListProps as MuiListProps } from '@mui/material/List';
import { styled } from '@mui/material/styles';
import { tokens } from '../tokens';

export type ListProps = MuiListProps;

const StyledList = styled(MuiList)({
  padding: 0,
  backgroundColor: tokens.colors.bg.level2,
  borderRadius: tokens.borderRadius.md,

  '& .MuiListItem-root': {
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    borderBottom: `1px solid ${tokens.colors.border.light}`,

    '&:last-child': {
      borderBottom: 'none',
    },
  },
});

export const List: React.FC<ListProps> = (props) => {
  return <StyledList {...props} />;
};

export default List;
