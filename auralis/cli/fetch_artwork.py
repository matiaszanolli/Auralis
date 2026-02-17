#!/usr/bin/env python3

"""
Fetch Artwork CLI
~~~~~~~~~~~~~~~~~

CLI command to fetch artist artwork from external sources and populate the database.

Usage:
    python -m auralis.cli.fetch_artwork [--discogs-token TOKEN] [--lastfm-key KEY]

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from auralis.library.manager import LibraryManager
from auralis.library.repositories.artist_repository import ArtistRepository
from auralis.services.artwork_service import ArtworkService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_artwork_for_all_artists(
    artist_repository: ArtistRepository,
    artwork_service: ArtworkService,
    force_refresh: bool = False
) -> dict:
    """
    Fetch artwork for all artists in the library.

    Args:
        artist_repository: Artist repository instance
        artwork_service: Artwork service instance
        force_refresh: If True, refetch even if artwork already exists

    Returns:
        Dict with statistics: {
            'total': int,
            'found': int,
            'not_found': int,
            'skipped': int,
            'errors': int
        }
    """
    stats = {
        'total': 0,
        'found': 0,
        'not_found': 0,
        'skipped': 0,
        'errors': 0
    }

    # Get all artists from repository
    artists = artist_repository.get_all_artists()
    stats['total'] = len(artists)

    logger.info(f"Found {len(artists)} artists in library")

    for i, artist in enumerate(artists, 1):
        logger.info(f"[{i}/{len(artists)}] Processing: {artist.name}")

        # Skip if artwork already exists and not forcing refresh
        if artist.artwork_url and not force_refresh:
            logger.info(f"  → Skipping (artwork already exists)")
            stats['skipped'] += 1
            continue

        try:
            # Fetch artwork
            result = artwork_service.fetch_artist_artwork(artist.name)

            if result:
                # Update artist with artwork info via repository
                success = artist_repository.update_artwork(
                    artist_id=artist.id,
                    artwork_url=result['artwork_url'],
                    artwork_source=result['source'],
                    artwork_fetched_at=datetime.now(timezone.utc)
                )

                if success:
                    logger.info(f"  ✓ Found artwork from {result['source']}")
                    stats['found'] += 1
                else:
                    logger.error(f"  ✗ Failed to update artist artwork")
                    stats['errors'] += 1
            else:
                logger.info(f"  ✗ No artwork found")
                stats['not_found'] += 1

        except Exception as e:
            logger.error(f"  ✗ Error fetching artwork: {e}")
            stats['errors'] += 1

    return stats


def main():
    """Main entry point for fetch_artwork CLI"""
    parser = argparse.ArgumentParser(
        description='Fetch artist artwork from external sources'
    )
    parser.add_argument(
        '--discogs-token',
        type=str,
        help='Discogs user token for API access'
    )
    parser.add_argument(
        '--lastfm-key',
        type=str,
        help='Last.fm API key'
    )
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force refresh even if artwork already exists'
    )
    parser.add_argument(
        '--library-path',
        type=str,
        help='Path to library database (default: ~/.auralis/library.db)'
    )

    args = parser.parse_args()

    # Initialize services
    try:
        # Get library path
        if args.library_path:
            library_path = Path(args.library_path)
        else:
            library_path = Path.home() / '.auralis' / 'library.db'

        # Initialize library manager
        logger.info(f"Loading library from: {library_path}")
        library_manager = LibraryManager(db_path=str(library_path))

        # Initialize artist repository
        artist_repository = ArtistRepository(
            session_factory=library_manager.get_session
        )

        # Initialize artwork service
        artwork_service = ArtworkService(
            discogs_token=args.discogs_token,
            lastfm_api_key=args.lastfm_key
        )

        # Log which sources are available
        sources = ['MusicBrainz (free)']
        if args.discogs_token:
            sources.append('Discogs')
        if args.lastfm_key:
            sources.append('Last.fm')

        logger.info(f"Available artwork sources: {', '.join(sources)}")

        # Fetch artwork
        logger.info("Starting artwork fetch...")
        stats = fetch_artwork_for_all_artists(
            artist_repository,
            artwork_service,
            force_refresh=args.force_refresh
        )

        # Print statistics
        print("\n" + "="*60)
        print("Artwork Fetch Complete")
        print("="*60)
        print(f"Total artists:    {stats['total']}")
        print(f"Artwork found:    {stats['found']}")
        print(f"Not found:        {stats['not_found']}")
        print(f"Skipped:          {stats['skipped']}")
        print(f"Errors:           {stats['errors']}")
        print("="*60)

        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
