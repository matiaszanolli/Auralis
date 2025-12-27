#!/usr/bin/env python3
"""
Phase 5 Scenario A: Cold Cache Testing
Tests fingerprint generation via gRPC when database has no cached fingerprint
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
)
logger = logging.getLogger('PHASE_5_TEST')

async def test_scenario_a() -> None:
    """
    Test Scenario A: Cold Cache (First Play)

    Expected flow:
    1. Track has no fingerprint in database
    2. System calls gRPC server to generate fingerprint
    3. Fingerprint is generated and stored in database
    4. Audio is streamed with fingerprint optimization
    """

    logger.info("=" * 80)
    logger.info("PHASE 5 - SCENARIO A: COLD CACHE (FIRST PLAY)")
    logger.info("=" * 80)

    # ========================================================================
    # PRE-TEST: Environment verification
    # ========================================================================
    logger.info("\n📋 PRE-TEST: Environment Verification")
    logger.info("-" * 80)

    # Check database
    try:
        import sqlite3
        db_path = Path.home() / '.auralis' / 'library.db'
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Count fingerprints
        cursor.execute("SELECT COUNT(*) FROM track_fingerprints")
        fp_count = cursor.fetchone()[0]
        logger.info(f"✅ Database accessible: {fp_count} fingerprints in database")

        # Check gRPC server
        cursor.execute("SELECT id, filepath FROM tracks LIMIT 1")
        test_track = cursor.fetchone()

        if test_track:
            test_track_id, test_track_path = test_track
            logger.info(f"✅ Test track found: ID={test_track_id}, Path={test_track_path}")
        else:
            logger.warning("⚠️  No tracks in database - cannot run test")
            return

        conn.close()
    except Exception as e:
        logger.error(f"❌ Database check failed: {e}")
        return

    # Check gRPC server
    try:
        import requests
        response = requests.get("http://localhost:50051/health", timeout=2)
        logger.info(f"✅ gRPC server reachable: {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️  gRPC server check failed: {e}")

    # ========================================================================
    # TEST: Fingerprint generation
    # ========================================================================
    logger.info("\n🔧 TEST: Fingerprint Generation via gRPC")
    logger.info("-" * 80)

    try:
        # Import fingerprint generator (fix import path)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from auralis.library.repositories.factory import RepositoryFactory
        from auralis.web.backend.fingerprint_generator import FingerprintGenerator

        # Setup database session
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        def get_session():
            return SessionLocal()

        def get_repository_factory():
            return RepositoryFactory(session_factory=SessionLocal)

        # Create fingerprint generator
        generator = FingerprintGenerator(
            session_factory=SessionLocal,
            get_repository_factory=get_repository_factory
        )

        logger.info(f"✅ FingerprintGenerator created")

        # Test fingerprint generation
        start_time = time.time()
        logger.info(f"\n📊 Starting fingerprint generation for track {test_track_id}")
        logger.info(f"   File: {test_track_path}")

        fingerprint_data = await generator.get_or_generate(
            track_id=test_track_id,
            filepath=test_track_path
        )

        elapsed = time.time() - start_time

        if fingerprint_data:
            logger.info(f"✅ Fingerprint generated successfully in {elapsed:.2f}s")
            logger.info(f"   LUFS: {fingerprint_data.get('lufs', 'N/A'):.2f}")
            logger.info(f"   Crest Factor: {fingerprint_data.get('crest_db', 'N/A'):.2f} dB")
            logger.info(f"   Dimensions: {len(fingerprint_data.get('dimensions', []))} (expected 25)")
        else:
            logger.warning(f"⚠️  Fingerprint generation returned None after {elapsed:.2f}s")

        # ====================================================================
        # VERIFY: Fingerprint stored in database
        # ====================================================================
        logger.info(f"\n📦 VERIFY: Fingerprint stored in database")
        logger.info("-" * 80)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT track_id, lufs, crest_db FROM track_fingerprints WHERE track_id = ?",
            (test_track_id,)
        )
        stored_fp = cursor.fetchone()

        if stored_fp:
            logger.info(f"✅ Fingerprint stored in database:")
            logger.info(f"   Track ID: {stored_fp[0]}")
            logger.info(f"   LUFS: {stored_fp[1]:.2f}")
            logger.info(f"   Crest Factor: {stored_fp[2]:.2f} dB")
        else:
            logger.warning(f"⚠️  Fingerprint NOT found in database after generation")

        conn.close()

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========================================================================
    # RESULTS SUMMARY
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("SCENARIO A: RESULTS")
    logger.info("=" * 80)

    logger.info(f"\n✅ SCENARIO A TEST COMPLETED")
    logger.info(f"   Duration: {elapsed:.2f} seconds")
    logger.info(f"   Fingerprint: {'Generated' if fingerprint_data else 'Failed'}")
    logger.info(f"   Stored: {'Yes' if stored_fp else 'No'}")
    logger.info(f"   Status: {'PASS' if fingerprint_data and stored_fp else 'FAIL'}")


if __name__ == "__main__":
    try:
        asyncio.run(test_scenario_a())
    except KeyboardInterrupt:
        logger.info("\n❌ Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
