import { describe, it, expect } from 'vitest';
import { groupAlbumsByEra, getEraLabel } from '../eraGrouping';

const album = (id: number, year?: number) => ({ id, year });

describe('eraGrouping', () => {
  describe('groupAlbumsByEra', () => {
    it('should group albums into 5-year eras by default', () => {
      const albums = [album(1, 2020), album(2, 2022), album(3, 2015)];
      const groups = groupAlbumsByEra(albums);

      expect(groups).toHaveLength(2);
      expect(groups[0].label).toBe('2020 - 2024');
      expect(groups[0].albums).toHaveLength(2);
      expect(groups[1].label).toBe('2015 - 2019');
      expect(groups[1].albums).toHaveLength(1);
    });

    it('should sort eras most recent first', () => {
      const albums = [album(1, 1990), album(2, 2010), album(3, 2000)];
      const groups = groupAlbumsByEra(albums);

      expect(groups.map((g) => g.startYear)).toEqual([2010, 2000, 1990]);
    });

    it('should sort albums within an era most recent first', () => {
      const albums = [album(1, 2020), album(2, 2024), album(3, 2021)];
      const groups = groupAlbumsByEra(albums);

      expect(groups[0].albums.map((a) => a.year)).toEqual([2024, 2021, 2020]);
    });

    it('should put albums without year in Unknown Year group at end', () => {
      const albums = [album(1, 2020), album(2), album(3)];
      const groups = groupAlbumsByEra(albums);

      expect(groups[groups.length - 1].label).toBe('Unknown Year');
      expect(groups[groups.length - 1].albums).toHaveLength(2);
      expect(groups[groups.length - 1].startYear).toBeUndefined();
    });

    it('should treat year 0 as unknown', () => {
      const albums = [album(1, 0)];
      const groups = groupAlbumsByEra(albums);

      expect(groups).toHaveLength(1);
      expect(groups[0].label).toBe('Unknown Year');
    });

    it('should treat year <= 1900 as unknown', () => {
      const albums = [album(1, 1899), album(2, 1900)];
      const groups = groupAlbumsByEra(albums);

      expect(groups).toHaveLength(1);
      expect(groups[0].label).toBe('Unknown Year');
    });

    it('should return empty array for empty input', () => {
      expect(groupAlbumsByEra([])).toEqual([]);
    });

    it('should support custom era span', () => {
      const albums = [album(1, 2020), album(2, 2025)];
      const groups = groupAlbumsByEra(albums, 10);

      expect(groups).toHaveLength(1);
      expect(groups[0].label).toBe('2020 - 2029');
    });

    it('should not create Unknown Year group when all albums have years', () => {
      const albums = [album(1, 2020)];
      const groups = groupAlbumsByEra(albums);

      expect(groups.every((g) => g.label !== 'Unknown Year')).toBe(true);
    });

    it('should set startYear and endYear on era groups', () => {
      const albums = [album(1, 2023)];
      const groups = groupAlbumsByEra(albums);

      expect(groups[0].startYear).toBe(2020);
      expect(groups[0].endYear).toBe(2024);
    });
  });

  describe('getEraLabel', () => {
    it('should return era label for a valid year', () => {
      expect(getEraLabel(2023)).toBe('2020 - 2024');
    });

    it('should return Unknown Year for undefined', () => {
      expect(getEraLabel(undefined)).toBe('Unknown Year');
    });

    it('should return Unknown Year for year < 1900', () => {
      expect(getEraLabel(1800)).toBe('Unknown Year');
    });

    it('should support custom era span', () => {
      expect(getEraLabel(2023, 10)).toBe('2020 - 2029');
    });
  });
});
