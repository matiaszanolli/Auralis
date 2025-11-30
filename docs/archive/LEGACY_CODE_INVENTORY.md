# Legacy Code Inventory & Archival Log

This document tracks legacy code identified in Auralis and the archival/removal process.

**Last Updated**: $(date)
**Status**: In Progress

## Table of Contents
1. [Identified Legacy Code](#identified-legacy-code)
2. [Archival Status](#archival-status)
3. [Removal Timeline](#removal-timeline)
4. [References](#references)

## Identified Legacy Code

### HIGH PRIORITY

#### 1. Legacy Config Module
- **Path**: `auralis/core/config/legacy.py`
- **Size**: 59 lines
- **Type**: Deprecated class definition
- **Status**: DEAD CODE - no production use
- **Why Legacy**: Replaced by `UnifiedConfig`, `PresetProfile`, `AdaptiveConfig`, `GenreProfile`
- **Safe to Remove**: YES - modern alternatives exist
- **Dependencies**:
  - `auralis-web/backend/main.py` (line 45) - test import
  - `tests/auralis/core/test_config.py` (line 9)
  - `tests/auralis/core/test_processor.py` (line 14)
- **Action**: REMOVE in next iteration

#### 2. Legacy Library Scanner
- **Path**: `auralis/library/scanner_legacy.py`
- **Size**: 513 lines
- **Type**: Superseded module
- **Status**: DEAD CODE - no production imports
- **Why Legacy**: Monolithic design replaced by modular `/auralis/library/scanner/` architecture
- **Safe to Remove**: YES - modern modular scanner fully replaces this
- **Modern Replacement**:
  - `auralis/library/scanner/scanner.py`
  - `auralis/library/scanner/config.py`
  - `auralis/library/scanner/batch_processor.py`
  - `auralis/library/scanner/file_discovery.py`
  - `auralis/library/scanner/metadata_extractor.py`
  - `auralis/library/scanner/audio_analyzer.py`
  - `auralis/library/scanner/duplicate_detector.py`
- **Action**: ARCHIVE to `docs/archive/legacy-code/library/`

### MEDIUM PRIORITY

#### 3. Simple AudioPlayer
- **Path**: `auralis/player/audio_player.py`
- **Size**: 179 lines
- **Type**: Duplicate implementation (simple version)
- **Status**: COEXISTS with modern EnhancedAudioPlayer
- **Modern Replacement**: `/auralis/player/enhanced_audio_player.py` (473 lines)
- **Used In**: Backend uses EnhancedAudioPlayer
- **Safe to Remove**: CONDITIONAL - if EnhancedAudioPlayer is fully production-ready
- **Action**: ARCHIVE if EnhancedAudioPlayer proven stable in production

#### 4. Alternative Audio Player Tests
- **Path**: `tests/auralis/player/test_audio_players_alt.py`
- **Size**: 590 lines
- **Type**: Alternative/experimental test implementation
- **Status**: Exists in parallel with standard tests
- **Purpose**: Unclear - likely testing deprecated AudioPlayer API
- **Action**: CONSOLIDATE with main test file or ARCHIVE if experimental

### LOW PRIORITY

#### 5. Old CI/CD Workflows
- **Paths**:
  - `.github/workflows/build.yml.old`
  - `.github/workflows/pythonpublish.yml.old`
- **Type**: Obsolete CI/CD configurations
- **Status**: DEAD CODE - marked with `.old` suffix
- **Action**: DELETE

## Archival Status

| File | Status | Date | Notes |
|------|--------|------|-------|
| `auralis/core/config/legacy.py` | ✅ DELETED | 2025-11-30 | Removed legacy Config class |
| `auralis/library/scanner_legacy.py` | ✅ ARCHIVED | 2025-11-30 | Moved to docs/archive/legacy-code/ |
| `.github/workflows/build.yml.old` | ✅ DELETED | 2025-11-30 | Removed obsolete CI/CD |
| `.github/workflows/pythonpublish.yml.old` | ✅ DELETED | 2025-11-30 | Removed obsolete CI/CD |
| `tests/auralis/core/test_config.py` | ✅ DELETED | 2025-11-30 | Tests for removed Config class |
| `tests/auralis/core/test_processor.py` | ✅ ARCHIVED | 2025-11-30 | Legacy batch processor tests |
| `tests/auralis/dsp/test_stages.py` | ✅ ARCHIVED | 2025-11-30 | Legacy DSP pipeline tests |
| `auralis/player/audio_player.py` | ✅ ARCHIVED | 2025-11-30 | Zero production usage; EnhancedAudioPlayer is standard |
| `tests/auralis/player/test_audio_player.py` | ✅ ARCHIVED | 2025-11-30 | Tests for removed AudioPlayer implementation |
| `tests/auralis/player/test_audio_players_alt.py` | ✅ DELETED | 2025-11-30 | Redundant duck-typing tests (590 lines) |

## Removal Timeline

### ✅ Phase 1: Safe Immediate Removal (COMPLETED 2025-11-30)
- ✅ Delete `.github/workflows/build.yml.old`
- ✅ Delete `.github/workflows/pythonpublish.yml.old`
- ✅ Remove legacy Config imports from main.py and test files
- ✅ Delete `auralis/core/config/legacy.py`
- ✅ Archive `auralis/library/scanner_legacy.py`
- ✅ Delete/archive legacy test files (test_config.py, test_processor.py, test_stages.py)
- ✅ Updated public API to export modern config system (UnifiedConfig, HybridProcessor, etc.)

**Impact**: Removed ~700 lines of legacy code and tests. All imports now point to modern system.

### ✅ Phase 2: Player Consolidation (COMPLETED 2025-11-30)
- ✅ Analyzed usage: AudioPlayer (180 lines) had ZERO production instantiations
- ✅ Confirmed EnhancedAudioPlayer is only player used in backend (main.py:255)
- ✅ Archived `auralis/player/audio_player.py` (not used anywhere)
- ✅ Deleted `tests/auralis/player/test_audio_players_alt.py` (590 lines of redundant duck-typing tests)
- ✅ Archived `tests/auralis/player/test_audio_player.py` (implementation-specific tests for removed AudioPlayer)
- ✅ Updated `auralis/player/__init__.py` to export EnhancedAudioPlayer only
- ✅ Updated `auralis/__init__.py` to consolidate player exports to EnhancedAudioPlayer
- ✅ Verified 33 passing tests in player module (all modern EnhancedAudioPlayer tests)

**Impact**: Removed 1,259 lines of duplicate/redundant code. Player API now unified on EnhancedAudioPlayer.

### Phase 3: Batch Processing Migration (Future)
- Legacy `process()` function still available for backward compatibility
- Can be fully deprecated once users migrate to HybridProcessor-based approach

## References

- **Modern Architecture**:
  - `auralis/core/config/` - Modern config system
  - `auralis/library/scanner/` - Modular scanner
  - `auralis/player/enhanced_audio_player.py` - Modern player

- **Related Issues**:
  - Audio enhancement system (Phase 9B)
  - Modular architecture consolidation (Phase 7.2)

- **Audit Date**: $(date)
- **Auditor**: Claude Code

