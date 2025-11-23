import React from 'react';
import {
  Box,
  List,
  ListItem,
  Skeleton
} from '@mui/material';
import { ListContainer } from '../Styles/ArtistList.styles';

/**
 * ArtistListLoading - Loading skeleton for artist list
 *
 * Displays:
 * - 15 skeleton items with avatar and text placeholders
 * - Maintains visual layout during initial data fetch
 */
export const ArtistListLoading: React.FC = () => {
  return (
    <ListContainer>
      <List>
        {[...Array(15)].map((_, index) => (
          <ListItem key={index}>
            <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', padding: '16px 20px' }}>
              <Skeleton variant="circular" width={56} height={56} sx={{ marginRight: '20px' }} />
              <Box sx={{ flex: 1 }}>
                <Skeleton variant="text" width="30%" height={24} />
                <Skeleton variant="text" width="50%" height={20} sx={{ marginTop: '8px' }} />
              </Box>
            </Box>
          </ListItem>
        ))}
      </List>
    </ListContainer>
  );
};

export default ArtistListLoading;
