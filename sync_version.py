#!/usr/bin/env python3
"""
Sync version across all project files.

Usage:
    python scripts/sync_version.py              # Sync current version
    python scripts/sync_version.py 1.0.0-beta.2  # Bump and sync to new version
"""

import re
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import auralis.version as version
except ImportError:
    print("❌ Error: Could not import auralis.version")
    print("Make sure you're running from project root: python scripts/sync_version.py")
    sys.exit(1)


def update_package_json(file_path: Path, new_version: str):
    """Update version in package.json file."""
    if not file_path.exists():
        print(f"⚠️  File not found: {file_path}")
        return False

    content = file_path.read_text()
    updated = re.sub(
        r'"version":\s*"[^"]*"',
        f'"version": "{new_version}"',
        content,
        count=1  # Only replace first occurrence
    )

    if content != updated:
        file_path.write_text(updated)
        print(f"✅ Updated {file_path}")
        return True
    else:
        print(f"ℹ️  No change needed in {file_path}")
        return False


def update_version_py(new_version: str):
    """Update version.py with new version."""
    version_file = Path("auralis/version.py")
    if not version_file.exists():
        print(f"❌ Version file not found: {version_file}")
        return False

    content = version_file.read_text()

    # Parse new version
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$', new_version)
    if not match:
        raise ValueError(f"Invalid version format: {new_version}")

    major, minor, patch, prerelease = match.groups()
    prerelease = prerelease or ""

    # Update __version__
    content = re.sub(
        r'__version__\s*=\s*"[^"]*"',
        f'__version__ = "{new_version}"',
        content
    )

    # Update __version_info__
    if prerelease:
        pre_parts = prerelease.split(".")
        pre_type = pre_parts[0]
        pre_num = int(pre_parts[1]) if len(pre_parts) > 1 else 0
        version_info = f'({major}, {minor}, {patch}, "{pre_type}", {pre_num})'
    else:
        version_info = f'({major}, {minor}, {patch})'

    content = re.sub(
        r'__version_info__\s*=\s*\([^)]+\)',
        f'__version_info__ = {version_info}',
        content
    )

    # Update __build_date__
    today = datetime.now().strftime("%Y-%m-%d")
    content = re.sub(
        r'__build_date__\s*=\s*"[^"]*"',
        f'__build_date__ = "{today}"',
        content
    )

    # Update VERSION_* constants
    content = re.sub(r'VERSION_MAJOR\s*=\s*\d+', f'VERSION_MAJOR = {major}', content)
    content = re.sub(r'VERSION_MINOR\s*=\s*\d+', f'VERSION_MINOR = {minor}', content)
    content = re.sub(r'VERSION_PATCH\s*=\s*\d+', f'VERSION_PATCH = {patch}', content)
    content = re.sub(
        r'VERSION_PRERELEASE\s*=\s*"[^"]*"',
        f'VERSION_PRERELEASE = "{prerelease}"',
        content
    )

    version_file.write_text(content)
    print(f"✅ Updated {version_file}")
    return True


def validate_version_format(version_str: str) -> bool:
    """Validate version string format."""
    pattern = r'^\d+\.\d+\.\d+(?:-(alpha|beta|rc)\.\d+)?$'
    return bool(re.match(pattern, version_str))


def main():
    """Main entry point."""
    print("=" * 60)
    print("Auralis Version Sync Tool")
    print("=" * 60)

    if len(sys.argv) > 1:
        new_version = sys.argv[1].lstrip('v')  # Remove leading 'v' if present

        # Validate version format
        if not validate_version_format(new_version):
            print(f"❌ Invalid version format: {new_version}")
            print("\nExpected format: MAJOR.MINOR.PATCH[-PRERELEASE]")
            print("Examples:")
            print("  - 1.0.0")
            print("  - 1.0.0-beta.1")
            print("  - 1.0.0-rc.2")
            print("  - 2.1.3")
            sys.exit(1)

        print(f"\n📦 Bumping version to {new_version}\n")
        update_version_py(new_version)
    else:
        new_version = version.__version__
        print(f"\n📦 Syncing current version {new_version} across project files\n")

    # Update all package.json files
    package_files = [
        Path("auralis-web/frontend/package.json"),
        Path("desktop/package.json"),
    ]

    updated_count = 0
    for file_path in package_files:
        if update_package_json(file_path, new_version):
            updated_count += 1

    print("\n" + "=" * 60)
    print(f"✅ Version sync complete: v{new_version}")
    print(f"   Updated {updated_count} package.json file(s)")
    print("=" * 60)

    if len(sys.argv) > 1:
        print("\n📋 Next steps:")
        print("1. Review changes: git diff")
        print(f"2. Commit: git commit -am 'chore: bump version to {new_version}'")
        print(f"3. Tag: git tag -a v{new_version} -m 'Release v{new_version}'")
        print(f"4. Push: git push origin master && git push origin v{new_version}")
        print("\n💡 Pushing the tag will trigger automated builds in CI/CD")
    else:
        print("\n💡 To bump to a new version, run:")
        print("   python scripts/sync_version.py <NEW_VERSION>")
        print("\n   Example: python scripts/sync_version.py 1.0.0-beta.2")


if __name__ == "__main__":
    main()
