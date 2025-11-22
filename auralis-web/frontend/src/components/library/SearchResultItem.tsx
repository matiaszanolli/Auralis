/**
 * SearchResultItem Component
 *
 * Renders a single search result item with avatar, title, subtitle,
 * and type chip. Consolidates result rendering logic from GlobalSearch.
 *
 * Features:
 * - Avatar support (album art, artist avatar, or icon)
 * - Title and subtitle text
 * - Type indicator chip (Track, Album, Artist)
 * - Click handler integration
 *
 * Usage:
 * ```tsx
 * <SearchResultItem
 *   result={result}
 *   avatar={getAvatar(result)}
 *   chipLabel="Track"
 *   chipClass="track"
 *   onClick={() => handleResultClick(result)}
 * />
 * ```
 */

import React from 'react';
import { ListItemAvatar, ListItemText } from '@mui/material';
import {
  StyledListItemButton,
  ResultTitle,
  ResultSubtitle,
  TypeChip
} from './SearchStyles.styles';

interface SearchResult {
  type: 'track' | 'album' | 'artist';
  id: number;
  title: string;
  subtitle?: string;
  albumId?: number;
}

interface SearchResultItemProps {
  result: SearchResult;
  avatar: React.ReactNode;
  chipLabel: string;
  chipClass: 'track' | 'album' | 'artist';
  onClick: (result: SearchResult) => void;
}

export const SearchResultItem: React.FC<SearchResultItemProps> = ({
  result,
  avatar,
  chipLabel,
  chipClass,
  onClick
}) => {
  return (
    <StyledListItemButton
      key={`${result.type}-${result.id}`}
      onClick={() => onClick(result)}
    >
      <ListItemAvatar>
        {avatar}
      </ListItemAvatar>
      <ListItemText
        primary={
          <ResultTitle className="result-title">
            {result.title}
          </ResultTitle>
        }
        secondary={<ResultSubtitle>{result.subtitle}</ResultSubtitle>}
      />
      <TypeChip label={chipLabel} size="small" className={chipClass} />
    </StyledListItemButton>
  );
};

export default SearchResultItem;
