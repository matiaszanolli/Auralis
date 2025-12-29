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
  // Transparent background for starfield visibility
  backgroundColor: 'transparent',
  borderRadius: tokens.borderRadius.md,

  '& .MuiListItem-root': {
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    // Glass bevel instead of hard border
    boxShadow: 'inset 0 -1px 0 rgba(255, 255, 255, 0.03)',

    '&:last-child': {
      boxShadow: 'none',
    },
  },
});

export const List: React.FC<ListProps> = (props) => {
  return <StyledList {...props} />;
};

export default List;
