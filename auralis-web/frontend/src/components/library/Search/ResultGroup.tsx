import React from 'react';
import { Divider } from '@mui/material';
import { CategoryHeader } from '../Styles/SearchStyles.styles';
import SearchResultItem from './SearchResultItem';

interface SearchResult {
  type: 'track' | 'album' | 'artist';
  id: number;
  title: string;
  subtitle?: string;
  albumId?: number;
}

interface ResultGroupProps {
  title: string;
  results: SearchResult[];
  showDivider: boolean;
  getAvatar: (result: SearchResult) => React.ReactNode;
  chipLabel: string;
  chipClass: 'track' | 'album' | 'artist';
  onResultClick: (result: SearchResult) => void;
}

/**
 * ResultGroup - Renders a grouped set of search results with category header
 *
 * Displays:
 * - Category header (Tracks, Albums, Artists)
 * - List of SearchResultItems
 * - Optional divider above group
 *
 * Manages rendering of results grouped by type
 */
export const ResultGroup: React.FC<ResultGroupProps> = ({
  title,
  results,
  showDivider,
  getAvatar,
  chipLabel,
  chipClass,
  onResultClick
}) => {
  if (results.length === 0) {
    return null;
  }

  return (
    <>
      {showDivider && <Divider sx={{ my: 1 }} />}
      <CategoryHeader>{title}</CategoryHeader>
      {results.map((result) => (
        <SearchResultItem
          key={`${result.type}-${result.id}`}
          result={result}
          avatar={getAvatar(result)}
          chipLabel={chipLabel}
          chipClass={chipClass}
          onClick={onResultClick}
        />
      ))}
    </>
  );
};

export default ResultGroup;
