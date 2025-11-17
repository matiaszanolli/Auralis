#!/usr/bin/env python3
"""Update profile based on feedback analysis.

This script applies feedback patterns to create new profile versions with
automatic validation. Each update is:
  1. Tested (runs unit tests to catch regressions)
  2. Committed (git adds the new profile version)
  3. Versioned (auto-increments version number)

Usage:
    ./scripts/update_profile.py studio --bass 1.8 --reason "user feedback"
    ./scripts/update_profile.py metal --treble 1.2 --reason "bright feedback"
    ./scripts/update_profile.py --apply-patterns  # Auto-detect patterns
"""

import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Optional
import sys


def find_latest_profile(profile_dir: Path, recording_type: str) -> Optional[Path]:
    """Find the latest version of a profile.

    Args:
        profile_dir: Directory containing profiles
        recording_type: Recording type (e.g., 'studio')

    Returns:
        Path to latest profile, or None if not found
    """
    # Look for patterns like "studio_hd_bright_v1.0.json"
    pattern = f"{recording_type}*_v*.json"
    matching_files = list(profile_dir.glob(pattern))

    if matching_files:
        # Sort by filename to get latest version
        return sorted(matching_files)[-1]

    return None


def parse_version(version_str: str) -> tuple:
    """Parse version string like "1.0" to (1, 0).

    Args:
        version_str: Version string

    Returns:
        Tuple of (major, minor)
    """
    try:
        parts = version_str.split(".")
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return 1, 0


def increment_version(version_str: str) -> str:
    """Increment patch version (1.0 → 1.1 → 1.2, etc.).

    Args:
        version_str: Current version string

    Returns:
        New version string
    """
    major, minor = parse_version(version_str)
    return f"{major}.{minor + 1}"


def load_profile(profile_path: Path) -> dict:
    """Load profile from JSON file.

    Args:
        profile_path: Path to profile JSON

    Returns:
        Profile dictionary
    """
    try:
        return json.loads(profile_path.read_text())
    except (json.JSONDecodeError, IOError) as e:
        print(f"✗ Could not load profile {profile_path}: {e}")
        sys.exit(1)


def save_profile(
    profile_path: Path,
    profile: dict,
    version: str,
) -> Path:
    """Save new profile version.

    Args:
        profile_path: Original profile path
        profile: Profile dictionary
        version: New version string

    Returns:
        Path to new profile file
    """
    # Extract base filename (e.g., "studio_hd_bright" from "studio_hd_bright_v1.0.json")
    stem = "_".join(profile_path.stem.split("_")[:-1])  # Remove "_vX.Y"

    # Create new versioned filename
    new_path = profile_path.parent / f"{stem}_v{version}.json"

    try:
        new_path.write_text(json.dumps(profile, indent=2))
        return new_path
    except IOError as e:
        print(f"✗ Could not save profile: {e}")
        sys.exit(1)


def run_tests() -> bool:
    """Run unit tests to validate profile changes.

    Returns:
        True if tests pass, False otherwise
    """
    print("\nRunning validation tests...", end=" ", flush=True)

    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/auralis/test_recording_type_detector.py", "-q"],
            capture_output=True,
            timeout=120,
            cwd=Path.cwd(),
        )

        if result.returncode == 0:
            print("✓ All tests pass")
            return True
        else:
            print("✗ Tests failed")
            # Print failure details
            if result.stdout:
                print("\nStdout:")
                print(result.stdout.decode())
            if result.stderr:
                print("\nStderr:")
                print(result.stderr.decode())
            return False

    except subprocess.TimeoutExpired:
        print("✗ Tests timed out")
        return False
    except Exception as e:
        print(f"✗ Could not run tests: {e}")
        return False


def commit_profile(profile_path: Path, reason: str) -> bool:
    """Commit profile update to git.

    Args:
        profile_path: Path to new profile file
        reason: Reason for update

    Returns:
        True if commit successful, False otherwise
    """
    print("Committing to git...", end=" ", flush=True)

    try:
        # Add file
        subprocess.run(
            ["git", "add", str(profile_path)],
            check=True,
            capture_output=True,
        )

        # Commit
        commit_msg = f"refactor: {profile_path.stem.replace('_', ' ')} - {reason}\n\n🤖 Generated with Auralis Phase 6.3 feedback learning system"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            check=True,
            capture_output=True,
        )

        print("✓ Committed")
        return True

    except subprocess.CalledProcessError as e:
        print("✗ Commit failed")
        if e.stderr:
            print(f"Error: {e.stderr.decode()}")
        return False
    except Exception as e:
        print(f"✗ Could not commit: {e}")
        return False


def update_profile(
    recording_type: str,
    adjustments: Dict[str, float],
    reason: str,
    data_dir: Optional[Path] = None,
    no_test: bool = False,
) -> bool:
    """Update a profile with new parameter values.

    Args:
        recording_type: Recording type (e.g., 'studio', 'metal')
        adjustments: Parameter adjustments {param: new_value}
        reason: Reason for update
        data_dir: Data directory (defaults to ~/.auralis)
        no_test: Skip test validation

    Returns:
        True if successful, False otherwise
    """
    # Determine data directory
    if data_dir is None:
        data_dir = Path.home() / ".auralis"

    # Look for profiles in multiple locations
    profile_dir = Path.cwd() / "data" / "profiles"
    if not profile_dir.exists():
        profile_dir = data_dir / "profiles"

    if not profile_dir.exists():
        print(f"✗ Could not find profile directory")
        print(f"  Checked: {Path.cwd() / 'data' / 'profiles'}")
        print(f"  Checked: {data_dir / 'profiles'}")
        return False

    # Find current profile
    current_profile_path = find_latest_profile(profile_dir, recording_type)

    if current_profile_path is None:
        print(f"✗ No profile found for {recording_type}")
        print(f"  Directory: {profile_dir}")
        return False

    # Load and parse current profile
    current_profile = load_profile(current_profile_path)
    current_version = current_profile_path.stem.split("_v")[-1]

    print(f"\nUpdating {recording_type} profile {current_version}", end="")

    # Increment version
    new_version = increment_version(current_version)
    print(f" → {new_version}")
    print("=" * 70)

    # Apply adjustments
    new_profile = current_profile.copy()
    for param, value in adjustments.items():
        if param in new_profile:
            old_value = new_profile[param]
            new_profile[param] = value
            print(f"  {param}: {old_value} → {value}")
        else:
            print(f"  (unknown param: {param})")

    # Validate profile
    if not new_profile:
        print("✗ Profile would be empty!")
        return False

    # Save new version
    new_profile_path = save_profile(current_profile_path, new_profile, new_version)
    print(f"\n✓ Profile saved: {new_profile_path.name}")

    # Run tests (unless skipped)
    if not no_test:
        if not run_tests():
            print("\n✗ Profile rejected due to test failure")
            new_profile_path.unlink()  # Delete the file
            return False

    # Commit to git
    if not commit_profile(new_profile_path, reason):
        print("\n✗ Could not commit profile (but file was saved)")
        return False

    # Success!
    print(f"\n✓ Profile {new_version} complete!")
    print(f"  File: {new_profile_path.name}")
    print(f"  Reason: {reason}")
    return True


def apply_patterns(data_dir: Optional[Path] = None) -> bool:
    """Auto-detect patterns and apply suggested adjustments.

    This is a placeholder that shows how to integrate with analyze_feedback.py
    In production, would parse feedback patterns and apply automatically.

    Args:
        data_dir: Data directory

    Returns:
        True if successful
    """
    print("Auto-detecting feedback patterns...")
    print("(This feature requires running analyze_feedback.py first)")
    print("\nExample:")
    print("  ./scripts/analyze_feedback.py --all-types")
    print("  ./scripts/update_profile.py studio --bass 1.8 --reason 'feedback pattern'")
    return False


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Update profiles based on feedback analysis",
        epilog="Examples:\n"
               "  ./scripts/update_profile.py studio --bass 1.8 --reason 'user feedback'\n"
               "  ./scripts/update_profile.py metal --treble 1.2 --reason 'harsh feedback'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "recording_type",
        nargs="?",
        help="Recording type to update (e.g., studio, metal, bootleg)"
    )
    parser.add_argument(
        "--bass",
        type=float,
        help="New bass_adjustment_db value"
    )
    parser.add_argument(
        "--mid",
        type=float,
        help="New mid_adjustment_db value"
    )
    parser.add_argument(
        "--treble",
        type=float,
        help="New treble_adjustment_db value"
    )
    parser.add_argument(
        "--reason",
        required=False,
        help="Reason for this update",
        default="Profile adjustment"
    )
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="Skip test validation (not recommended)"
    )
    parser.add_argument(
        "--apply-patterns",
        action="store_true",
        help="Auto-apply detected feedback patterns"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Data directory (defaults to ~/.auralis)",
        default=None,
    )

    args = parser.parse_args()

    # Handle auto-patterns mode
    if args.apply_patterns:
        return apply_patterns(args.data_dir)

    # Validate inputs
    if not args.recording_type:
        parser.print_help()
        return False

    # Collect adjustments
    adjustments = {}
    if args.bass is not None:
        adjustments["bass_adjustment_db"] = args.bass
    if args.mid is not None:
        adjustments["mid_adjustment_db"] = args.mid
    if args.treble is not None:
        adjustments["treble_adjustment_db"] = args.treble

    if not adjustments:
        print("Error: Must specify at least one parameter (--bass, --mid, or --treble)")
        parser.print_help()
        return False

    # Update profile
    success = update_profile(
        args.recording_type,
        adjustments,
        args.reason,
        args.data_dir,
        args.no_test
    )

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
