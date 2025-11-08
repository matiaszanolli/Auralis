# Documentation Cleanup Plan - October 31, 2025

## Current State
**43 markdown files in root directory** - needs organization

---

## Categorization

### ✅ KEEP IN ROOT (8 files - Essential)

These files should remain in root as they are actively referenced and essential for developers:

1. **README.md** - Primary project documentation
2. **CLAUDE.md** - Claude Code instructions (actively used)
3. **BETA8_P0_PRIORITIES.md** - Current priorities (Oct 30, actively worked on)
4. **BETA6_KEYBOARD_SHORTCUTS_DISABLED.md** - Current known issue (Oct 30)
5. **BETA_USER_GUIDE.md** - User-facing guide
6. **RELEASE_NOTES_BETA6.md** - Latest release notes (Oct 30)
7. **MASTER_ROADMAP.md** - High-level roadmap
8. **PRIORITY1_QUICK_REFERENCE.md** - Quick reference for P1 issues

---

### 📁 MOVE TO docs/sessions/ (17 files - Session Documentation)

These belong in session-specific directories:

#### → docs/sessions/oct28_beta4_tests/
1. **BETA4_CRITICAL_ISSUES.md** (Oct 28)
2. **BETA4_REMAINING_TEST_ISSUES.md** (Oct 28)
3. **BETA4_TEST_FIX_COMPLETE.md** (Oct 28)
4. **BETA4_TEST_FIX_FINAL.md** (Oct 28)
5. **BETA4_TEST_FIX_PROGRESS.md** (Oct 28)

#### → docs/sessions/oct28_beta5_release/
6. **BUILD_BETA5_COMPLETE.md** (Oct 28)
7. **BUILD_SUMMARY_BETA5.md** (Oct 30)
8. **RELEASE_NOTES_BETA5.md** (Oct 30)
9. **RELEASE_NOTES_BETA5_FINGERPRINT.md** (Oct 28)
10. **KNOWN_ISSUES_BETA5.md** (needs checking)

#### → docs/sessions/oct28_fingerprint_phase2/ (already exists)
11. **FINGERPRINT_PHASE2_FINAL_REPORT.md** (Oct 28)
12. **FINGERPRINT_PHASE2_FINAL_STATUS.md** (Oct 28)
13. **FINGERPRINT_PHASE2_SESSION1.md** (Oct 28)

#### → docs/sessions/oct30_beta6_phase2_interactions/
14. **PHASE2_BATCH_OPERATIONS_COMPLETE.md** (Oct 30)
15. **PHASE2_CONTEXT_MENUS_COMPLETE.md** (Oct 30)
16. **PHASE2_DRAG_DROP_COMPLETE.md** (Oct 30)
17. **PHASE2_KEYBOARD_SHORTCUTS_COMPLETE.md** (Oct 30)

#### → docs/sessions/oct30_beta6_hotfix/ (already exists - check for duplicates)
18. **HOTFIX_BETA6_CIRCULAR_DEPENDENCY.md**

#### → Appropriate session directories (oct29, oct30)
19. **SESSION_SUMMARY_OCT29_TESTS_AND_25D.md** (Oct 29)
20. **SESSION_SUMMARY_OCT29_TEST_IMPROVEMENTS.md** (Oct 29)
21. **SESSION_SUMMARY_OCT30_CONTEXT_MENUS_PHASE2.md** (Oct 30)
22. **SESSION_SUMMARY_OCT30_TEST_COVERAGE.md** (Oct 30)
23. **SESSION_SUMMARY_OCT30_UI_POLISH_PHASE1.md** (Oct 30)

---

### 📦 MOVE TO docs/completed/ or docs/guides/ (10 files)

#### → docs/completed/ (Completed features)
1. **25D_SIDECAR_IMPLEMENTATION_COMPLETE.md**
2. **SIDECAR_TESTS_COMPLETE.md**
3. **SIMILARITY_API_FIXES_COMPLETE.md**
4. **FRONTEND_TEST_COVERAGE_COMPLETE.md**
5. **GENERAL_TEST_COVERAGE_COMPLETE.md**

#### → docs/guides/ (Implementation guides)
6. **CONTEXT_MENU_GUIDE.md**
7. **DRAG_DROP_BACKEND_API.md**
8. **DRAG_DROP_INTEGRATION_GUIDE.md**

#### → docs/troubleshooting/ (Bug fixes)
9. **SIDEBAR_NAVIGATION_FIX.md**

#### → docs/archive/ (Planning docs, no longer current)
10. **TEST_AUDIT_AND_ACTION_PLAN.md**

---

### 🗑️ DELETE (8 files - Obsolete/Redundant)

These are superseded by more recent documentation or already covered elsewhere:

1. **BUG_FIXES_AND_POLISH_OCT30.md** - Superseded by PHASE2_*.md files
2. **DOCUMENTATION_ORGANIZED_OCT26.md** - Obsolete organization doc (Oct 26)

**Check for duplication before deletion**:
3-8. Various session summaries and completion docs may duplicate content in docs/sessions/

---

## Implementation Steps

### Phase 1: Create Missing Session Directories
```bash
mkdir -p docs/sessions/oct28_beta4_tests
mkdir -p docs/sessions/oct28_beta5_release
mkdir -p docs/sessions/oct30_beta6_phase2_interactions
```

### Phase 2: Move Session Documentation
```bash
# Beta 4 tests
mv BETA4_*.md docs/sessions/oct28_beta4_tests/

# Beta 5 release
mv BUILD_BETA5_COMPLETE.md BUILD_SUMMARY_BETA5.md docs/sessions/oct28_beta5_release/
mv RELEASE_NOTES_BETA5*.md KNOWN_ISSUES_BETA5.md docs/sessions/oct28_beta5_release/

# Fingerprint Phase 2 (check if directory already has these)
mv FINGERPRINT_PHASE2_*.md docs/sessions/oct28_fingerprint_phase2/

# Beta 6 Phase 2 interactions
mv PHASE2_*.md docs/sessions/oct30_beta6_phase2_interactions/

# Session summaries
mv SESSION_SUMMARY_OCT29_*.md docs/sessions/oct29_*/
mv SESSION_SUMMARY_OCT30_*.md docs/sessions/oct30_*/

# Hotfix
mv HOTFIX_BETA6_CIRCULAR_DEPENDENCY.md docs/sessions/oct30_beta6_hotfix/
```

### Phase 3: Move Completed Features and Guides
```bash
# Completed features
mv 25D_SIDECAR_IMPLEMENTATION_COMPLETE.md docs/completed/
mv SIDECAR_TESTS_COMPLETE.md docs/completed/
mv SIMILARITY_API_FIXES_COMPLETE.md docs/completed/
mv FRONTEND_TEST_COVERAGE_COMPLETE.md docs/completed/
mv GENERAL_TEST_COVERAGE_COMPLETE.md docs/completed/

# Guides
mv CONTEXT_MENU_GUIDE.md docs/guides/
mv DRAG_DROP_BACKEND_API.md docs/guides/
mv DRAG_DROP_INTEGRATION_GUIDE.md docs/guides/

# Troubleshooting
mv SIDEBAR_NAVIGATION_FIX.md docs/troubleshooting/

# Archive
mv TEST_AUDIT_AND_ACTION_PLAN.md docs/archive/
```

### Phase 4: Delete Obsolete Files
```bash
# After verifying no valuable content lost
rm BUG_FIXES_AND_POLISH_OCT30.md
rm DOCUMENTATION_ORGANIZED_OCT26.md
```

### Phase 5: Update docs/README.md
- Add new session directories to index
- Update completed features section
- Add new guides

---

## Expected Result

**Root directory**: 8 essential files only
- README.md
- CLAUDE.md
- BETA8_P0_PRIORITIES.md
- BETA6_KEYBOARD_SHORTCUTS_DISABLED.md
- BETA_USER_GUIDE.md
- RELEASE_NOTES_BETA6.md
- MASTER_ROADMAP.md
- PRIORITY1_QUICK_REFERENCE.md

**docs/sessions/**: Well-organized session-specific documentation
**docs/completed/**: Completed feature documentation
**docs/guides/**: Implementation guides
**docs/troubleshooting/**: Bug fix documentation
**docs/archive/**: Historical planning documents

---

## Validation

After cleanup:
```bash
# Should show ~8 files
ls -1 *.md | wc -l

# Should be well-organized
tree docs/
```

---

**Status**: Plan created, ready for implementation
**Risk**: Low (all moves, minimal deletes)
**Time**: ~15 minutes
