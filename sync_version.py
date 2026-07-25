#!/usr/bin/env python3
"""
Sync version across all project files.

Usage:
    python sync_version.py               # Sync current version
    python sync_version.py 1.0.0-beta.2  # Bump and sync to new version
"""

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Add the repository root to the import path regardless of the caller's cwd.
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from auralis import version
except ImportError:
    print("❌ Error: Could not import auralis.version")
    print("Make sure the repository is readable and auralis.version can be imported")
    sys.exit(1)


def update_package_json(file_path: Path, new_version: str):
    """Update version in package.json file."""
    target = PROJECT_ROOT / file_path
    if not target.exists():
        print(f"⚠️  File not found: {file_path}")
        return False

    content = target.read_text()
    updated = re.sub(
        r'"version":\s*"[^"]*"',
        f'"version": "{new_version}"',
        content,
        count=1  # Only replace first occurrence
    )

    if content != updated:
        target.write_text(updated)
        print(f"✅ Updated {file_path}")
        return True
    else:
        print(f"ℹ️  No change needed in {file_path}")
        return False


def update_version_py(new_version: str, build_date: str):
    """Update the canonical product version and compatibility mirror."""
    version_file = PROJECT_ROOT / "auralis/version.py"
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
        version_info = f'({major}, {minor}, {patch}, "", 0)'

    content = re.sub(
        r'__version_info__\s*=\s*\([^)]+\)',
        f'__version_info__ = {version_info}',
        content
    )

    # Update __build_date__
    content = re.sub(
        r'__build_date__\s*=\s*"[^"]*"',
        f'__build_date__ = "{build_date}"',
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

    compatibility_file = PROJECT_ROOT / "auralis/__version__.py"
    compatibility = compatibility_file.read_text()
    compatibility = re.sub(
        r'__version__\s*=\s*"[^"]*"',
        f'__version__ = "{new_version}"',
        compatibility,
        count=1,
    )
    compatibility = re.sub(
        r'__version_info__\s*=\s*\([^)]+\)',
        f'__version_info__ = {version_info}',
        compatibility,
        count=1,
    )
    compatibility_file.write_text(compatibility)
    print("✅ Updated auralis/__version__.py compatibility mirror")
    return True


def update_pyproject(new_version: str):
    """Update the Python package metadata mirror."""
    pyproject_file = PROJECT_ROOT / "pyproject.toml"
    content = pyproject_file.read_text()
    updated = re.sub(
        r'(?m)^version\s*=\s*"[^"]*"(?:\s*#.*)?$',
        (
            f'version = "{new_version}"  # PEP 440 mirror of the '
            "auralis/version.py source of truth"
        ),
        content,
        count=1,
    )
    if content == updated:
        print("ℹ️  No change needed in pyproject.toml")
        return False
    pyproject_file.write_text(updated)
    print("✅ Updated pyproject.toml")
    return True


def update_health_fallback(new_version: str, build_date: str):
    """Update the degraded-build /api/version fallback."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$', new_version)
    if not match:
        raise ValueError(f"Invalid version format: {new_version}")

    major, minor, patch, prerelease = match.groups()
    prerelease = prerelease or ""
    health_file = PROJECT_ROOT / "auralis-web/backend/routers/health.py"
    content = health_file.read_text()
    updated = content
    replacements = (
        (r'(\s+version=)"[^"]*"', rf'\g<1>"{new_version}"'),
        (r'(\s+major=)\d+', rf'\g<1>{major}'),
        (r'(\s+minor=)\d+', rf'\g<1>{minor}'),
        (r'(\s+patch=)\d+', rf'\g<1>{patch}'),
        (r'(\s+prerelease=)"[^"]*"', rf'\g<1>"{prerelease}"'),
        (r'(\s+build_date=)"[^"]*"', rf'\g<1>"{build_date}"'),
        (r'(\s+display=)"[^"]*"', rf'\g<1>"Auralis v{new_version}"'),
    )
    for pattern, replacement in replacements:
        updated = re.sub(pattern, replacement, updated, count=1)

    if content == updated:
        print("ℹ️  No change needed in backend version fallback")
        return False
    health_file.write_text(updated)
    print("✅ Updated backend version fallback")
    return True


def update_dockerfile(new_version: str):
    """Update the container image metadata mirror."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    content = dockerfile.read_text()
    updated = re.sub(
        r'(?m)^LABEL version="[^"]*"$',
        f'LABEL version="{new_version}"',
        content,
        count=1,
    )
    if content == updated:
        print("ℹ️  No change needed in Dockerfile")
        return False
    dockerfile.write_text(updated)
    print("✅ Updated Dockerfile")
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
        build_date = datetime.now(UTC).date().isoformat()

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
        update_version_py(new_version, build_date)
    else:
        new_version = version.__version__
        build_date = version.__build_date__
        print(f"\n📦 Syncing current version {new_version} across project files\n")

    # Update all derived version surfaces.
    package_files = [
        Path("package.json"),
        Path("auralis-web/frontend/package.json"),
        Path("desktop/package.json"),
    ]

    updated_count = 0
    for file_path in package_files:
        if update_package_json(file_path, new_version):
            updated_count += 1
    if update_pyproject(new_version):
        updated_count += 1
    if update_health_fallback(new_version, build_date):
        updated_count += 1
    if update_dockerfile(new_version):
        updated_count += 1

    print("\n" + "=" * 60)
    print(f"✅ Version sync complete: v{new_version}")
    print(f"   Updated {updated_count} derived file(s)")
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
        print("   python sync_version.py <NEW_VERSION>")
        print("\n   Example: python sync_version.py 1.5.1")


if __name__ == "__main__":
    main()
