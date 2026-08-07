#!/usr/bin/env python3
"""Test the version management system"""

import shutil
import tempfile
from pathlib import Path

print("🧪 Testing Version Management System\n")

# Test 1: Version info
print("1️⃣  Testing version imports...")
try:
    from auralis.__version__ import __db_schema_version__, __version__, __version_info__
    print(f"   ✅ Package version: {__version__}")
    print(f"   ✅ Version info: {__version_info__}")
    print(f"   ✅ DB schema version: {__db_schema_version__}")
except ImportError as e:
    print(f"   ❌ Failed to import version: {e}")
    exit(1)

# Test 2: Backend version
print("\n2️⃣  Testing backend version...")
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "auralis-web" / "backend"))
    from version import get_version_info
    version_info = get_version_info()
    print(f"   ✅ API version: {version_info['api_version']}")
    print(f"   ✅ DB schema: {version_info['db_schema_version']}")
    print(f"   ✅ Min client: {version_info['min_client_version']}")
except ImportError as e:
    print(f"   ❌ Failed to import backend version: {e}")
    exit(1)

# Test 3: Migration Manager
print("\n3️⃣  Testing MigrationManager...")
try:
    from auralis.library.migrations import MigrationManager, backup_database

    # Create temporary database
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"

    print(f"   📁 Created temp DB: {db_path}")

    # Initialize manager
    manager = MigrationManager(str(db_path))
    print(f"   ✅ MigrationManager initialized")

    # Check version (should be 0 for fresh DB)
    version = manager.get_current_version()
    print(f"   ✅ Current version: {version} (expected 0)")
    assert version == 0, f"Expected version 0, got {version}"

    # Initialize fresh database
    success = manager.initialize_fresh_database()
    print(f"   ✅ Fresh database initialized: {success}")
    assert success is True

    # Check version again
    version = manager.get_current_version()
    print(f"   ✅ New version: {version} (expected {__db_schema_version__})")
    assert version == __db_schema_version__

    manager.close()

    # Test backup
    print("\n4️⃣  Testing backup system...")
    backup_path = backup_database(str(db_path))
    print(f"   ✅ Backup created: {Path(backup_path).name}")
    assert Path(backup_path).exists()

    # Cleanup
    shutil.rmtree(temp_dir)
    print("   ✅ Cleanup complete")

except Exception as e:
    print(f"   ❌ Migration test failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 4: Library Manager integration
print("\n5️⃣  Testing LibraryDatabase integration...")
try:
    from auralis.library import LibraryDatabase

    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "library.db"

    # Initialize library database (should trigger migration)
    print("   🔄 Initializing LibraryDatabase (will trigger migration)...")
    db = LibraryDatabase(str(db_path))
    print("   ✅ LibraryDatabase initialized successfully")

    # Verify database version
    from auralis.library.migrations import MigrationManager
    mig_manager = MigrationManager(str(db_path))
    version = mig_manager.get_current_version()
    print(f"   ✅ Database version: {version}")
    assert version == __db_schema_version__
    mig_manager.close()

    # Cleanup
    shutil.rmtree(temp_dir)
    print("   ✅ Integration test complete")

except Exception as e:
    print(f"   ❌ LibraryDatabase integration failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "="*60)
print("🎉 All version management tests passed!")
print("="*60)
print("\n✅ Version system is working correctly")
print(f"✅ Package version: {__version__}")
print(f"✅ DB schema version: {__db_schema_version__}")
print("✅ Migration system: Operational")
print("✅ Backup system: Operational")
print("✅ LibraryDatabase integration: Complete")
print("\n🚀 Auralis is ready for production launch!")
