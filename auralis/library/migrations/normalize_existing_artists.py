"""
Artist Normalization Migration Script

One-time migration to normalize existing artist data:
1. Compute normalized_name for all existing artists
2. Find duplicates (artists with same normalized_name)
3. Merge duplicates: update track_artist and album references
4. Delete redundant artist records

Run this after applying migration_v010_to_v011.sql

Usage:
    python -m auralis.library.migrations.normalize_existing_artists

@module auralis.library.migrations.normalize_existing_artists
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.library.utils.artist_normalizer import normalize_artist_name


def get_database_path() -> Path:
    """Get the database path from user home directory"""
    return Path.home() / '.auralis' / 'library.db'


def normalize_existing_artists(db_path: Path | None = None, dry_run: bool = False) -> Dict[str, any]:
    """
    Normalize existing artist data in the database.

    Args:
        db_path: Path to SQLite database (default: ~/.auralis/library.db)
        dry_run: If True, don't commit changes, just report what would happen

    Returns:
        Dictionary with migration statistics
    """
    if db_path is None:
        db_path = get_database_path()

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return {'error': 'Database not found'}

    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    session = Session()

    stats = {
        'total_artists': 0,
        'artists_updated': 0,
        'duplicates_found': 0,
        'artists_merged': 0,
        'artists_deleted': 0,
        'tracks_updated': 0,
        'albums_updated': 0,
    }

    try:
        # Phase 1: Compute normalized_name for all artists
        print("Phase 1: Computing normalized names for all artists...")

        artists = session.execute(text("SELECT id, name FROM artists")).fetchall()
        stats['total_artists'] = len(artists)

        for artist_id, name in artists:
            normalized = normalize_artist_name(name)
            if not dry_run:
                session.execute(
                    text("UPDATE artists SET normalized_name = :normalized WHERE id = :id"),
                    {'normalized': normalized, 'id': artist_id}
                )
            stats['artists_updated'] += 1

        if not dry_run:
            session.commit()

        print(f"  Updated {stats['artists_updated']} artists with normalized names")

        # Phase 2: Find duplicates (same normalized_name)
        print("\nPhase 2: Finding duplicate artists...")

        duplicates = session.execute(text("""
            SELECT normalized_name, GROUP_CONCAT(id) as ids, GROUP_CONCAT(name) as names
            FROM artists
            WHERE normalized_name IS NOT NULL AND normalized_name != ''
            GROUP BY normalized_name
            HAVING COUNT(*) > 1
            ORDER BY normalized_name
        """)).fetchall()

        stats['duplicates_found'] = len(duplicates)
        print(f"  Found {stats['duplicates_found']} groups of duplicate artists")

        # Phase 3: Merge duplicates
        if duplicates:
            print("\nPhase 3: Merging duplicate artists...")

            for normalized_name, id_list, name_list in duplicates:
                ids = [int(x) for x in id_list.split(',')]
                names = name_list.split(',')

                # Pick canonical artist (the one with most tracks, or first one)
                track_counts = []
                for artist_id in ids:
                    count_result = session.execute(
                        text("SELECT COUNT(*) FROM track_artist WHERE artist_id = :id"),
                        {'id': artist_id}
                    ).scalar()
                    track_counts.append((artist_id, count_result))

                # Sort by track count descending, take first as canonical
                track_counts.sort(key=lambda x: x[1], reverse=True)
                canonical_id = track_counts[0][0]
                duplicate_ids = [x[0] for x in track_counts[1:]]

                canonical_name = session.execute(
                    text("SELECT name FROM artists WHERE id = :id"),
                    {'id': canonical_id}
                ).scalar()

                duplicate_names = [n for i, n in zip(ids, names) if i != canonical_id]

                print(f"  Merging: {duplicate_names} -> '{canonical_name}' (id={canonical_id})")

                if not dry_run:
                    # Update track_artist references
                    for dup_id in duplicate_ids:
                        # Check if canonical already has the track association
                        # to avoid duplicate key errors
                        session.execute(text("""
                            UPDATE OR IGNORE track_artist
                            SET artist_id = :canonical_id
                            WHERE artist_id = :dup_id
                        """), {'canonical_id': canonical_id, 'dup_id': dup_id})

                        # Delete any remaining references (duplicates that couldn't be updated)
                        deleted = session.execute(
                            text("DELETE FROM track_artist WHERE artist_id = :dup_id"),
                            {'dup_id': dup_id}
                        )
                        stats['tracks_updated'] += deleted.rowcount

                    # Update album references
                    for dup_id in duplicate_ids:
                        updated = session.execute(text("""
                            UPDATE albums
                            SET artist_id = :canonical_id
                            WHERE artist_id = :dup_id
                        """), {'canonical_id': canonical_id, 'dup_id': dup_id})
                        stats['albums_updated'] += updated.rowcount

                    # Delete duplicate artists
                    for dup_id in duplicate_ids:
                        session.execute(
                            text("DELETE FROM artists WHERE id = :id"),
                            {'id': dup_id}
                        )
                        stats['artists_deleted'] += 1

                stats['artists_merged'] += len(duplicate_ids)

            if not dry_run:
                session.commit()

        print("\n" + "=" * 50)
        print("Migration Summary:")
        print(f"  Total artists: {stats['total_artists']}")
        print(f"  Artists normalized: {stats['artists_updated']}")
        print(f"  Duplicate groups found: {stats['duplicates_found']}")
        print(f"  Artists merged: {stats['artists_merged']}")
        print(f"  Artists deleted: {stats['artists_deleted']}")
        print(f"  Track associations updated: {stats['tracks_updated']}")
        print(f"  Albums updated: {stats['albums_updated']}")

        if dry_run:
            print("\n[DRY RUN] No changes were committed to the database")

        return stats

    except Exception as e:
        session.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        session.close()


def main():
    """Command-line entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Normalize existing artist data')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without committing')
    parser.add_argument('--db', type=Path, default=None,
                        help='Path to database (default: ~/.auralis/library.db)')

    args = parser.parse_args()

    print("Artist Normalization Migration")
    print("=" * 50)

    if args.dry_run:
        print("[DRY RUN MODE - No changes will be saved]")

    normalize_existing_artists(db_path=args.db, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
