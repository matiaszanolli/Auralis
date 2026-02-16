# Security Fix: Artwork Path Validation (Issue #2237)

**Date**: 2026-02-16
**Severity**: HIGH
**CVE**: N/A (internal project)
**Status**: FIXED

## Vulnerability Description

The `GET /api/albums/{album_id}/artwork` endpoint served files directly from the `album.artwork_path` database field without validating that the path was within the allowed artwork directory (`~/.auralis/artwork/`).

If the database was tampered with (via SQL injection from issue #2078 or malicious update endpoints), an attacker could:
1. Set `artwork_path` to any file on the filesystem (e.g., `/etc/passwd`)
2. Request the artwork via the API
3. Receive the contents of the arbitrary file

## Root Cause

The endpoint only checked if the file exists, not whether it's within the allowed directory:

```python
# VULNERABLE CODE
if not album.artwork_path or not Path(album.artwork_path).exists():
    raise HTTPException(status_code=404, detail="Artwork not found")

return FileResponse(album.artwork_path, media_type="image/jpeg")  # NO VALIDATION
```

## Attack Scenarios

### Scenario 1: SQL Injection + Arbitrary File Read
```sql
-- Attacker uses SQL injection (issue #2078) to tamper artwork_path
UPDATE albums SET artwork_path = '/etc/passwd' WHERE id = 1;
```
```bash
# Then requests the "artwork"
curl http://localhost:8765/api/albums/1/artwork
# Receives contents of /etc/passwd
```

### Scenario 2: Symlink Attack
```bash
# Attacker creates symlink in artwork directory pointing to sensitive file
ln -s /etc/passwd ~/.auralis/artwork/evil.jpg

# Updates album artwork_path via legitimate update endpoint
curl -X POST http://localhost:8765/api/albums/1/artwork/upload \
  -F "file=@evil.jpg"

# Requests artwork
curl http://localhost:8765/api/albums/1/artwork
# Receives contents of /etc/passwd via symlink
```

## Fix Implementation

### Security Measures Added

1. **Path Resolution with Symlink Handling**
   - Use `Path.resolve(strict=False)` to resolve symlinks and relative paths
   - Resolves path even if file doesn't exist (for security validation)

2. **Directory Containment Check**
   - Validate that resolved path is within `~/.auralis/artwork/`
   - Use `is_relative_to()` for safe path comparison
   - Reject paths outside allowed directory with 403 Forbidden

3. **Defense in Depth**
   - Validate path BEFORE checking file existence
   - Return 403 for security violations (not 404)
   - Log all path traversal attempts for monitoring

### Secure Code

```python
# Security: Validate artwork path is within allowed directory
artwork_dir = Path.home() / ".auralis" / "artwork"
artwork_dir.mkdir(parents=True, exist_ok=True)

# Resolve allowed directory (handles symlinks in base path)
allowed_dir = artwork_dir.resolve()

# Resolve artwork path (handles symlinks and relative paths)
# Use strict=False to resolve path even if file doesn't exist (for security validation)
try:
    requested_path = Path(album.artwork_path).resolve(strict=False)
except (OSError, RuntimeError) as e:
    logger.warning(f"Invalid artwork path for album {album_id}: {album.artwork_path} - {e}")
    raise HTTPException(status_code=403, detail="Access denied: invalid path")

# Security: Check that resolved path is within allowed directory
# This MUST happen before existence check to prevent path traversal
if not requested_path.is_relative_to(allowed_dir):
    logger.warning(
        f"Path traversal attempt blocked for album {album_id}: "
        f"requested={requested_path}, allowed_dir={allowed_dir}"
    )
    raise HTTPException(status_code=403, detail="Access denied: path outside artwork directory")

# Additional check: file must exist (after security validation)
if not requested_path.exists():
    raise HTTPException(status_code=404, detail="Artwork not found")

return FileResponse(str(requested_path), media_type="image/jpeg", ...)
```

## Files Modified

- `auralis-web/backend/routers/artwork.py`:
  - Lines 74-124: Added comprehensive path validation
  - Security comments explaining each step
- `tests/backend/test_artwork_path_validation.py`: (NEW)
  - 12 unit tests for path validation logic
  - Tests all attack vectors (absolute paths, relative traversal, symlinks)

## Testing

### Unit Tests (12 tests) ✅

Path validation logic tested comprehensively:

1. ✅ Valid paths within allowed directory accepted
2. ✅ Absolute paths outside directory rejected (`/etc/passwd`)
3. ✅ Relative path traversal rejected (`../../etc/passwd`)
4. ✅ Symlinks outside directory rejected
5. ✅ Paths with dot segments normalized (`.` and `..`)
6. ✅ Nested subdirectories within allowed directory accepted
7. ✅ Symlinks in allowed directory itself handled correctly
8. ✅ Null bytes in paths rejected
9. ✅ Empty paths rejected
10. ✅ Root path rejected (`/`)
11. ✅ Home directory rejected
12. ✅ Parent directory rejected (`~/.auralis`)

```bash
# Run path validation tests
python -m pytest tests/backend/test_artwork_path_validation.py -v
# Result: 12 passed ✅
```

### Manual Verification

```bash
# Test 1: Valid artwork path (should succeed)
# 1. Create valid artwork
mkdir -p ~/.auralis/artwork
echo "fake jpeg" > ~/.auralis/artwork/test.jpg

# 2. Update album artwork_path in database
sqlite3 ~/.auralis/library.db "UPDATE albums SET artwork_path = '$HOME/.auralis/artwork/test.jpg' WHERE id = 1;"

# 3. Request artwork
curl http://localhost:8765/api/albums/1/artwork
# Expected: 200 OK, returns file contents

# Test 2: Path traversal attack (should be blocked)
# 1. Tamper database with malicious path
sqlite3 ~/.auralis/library.db "UPDATE albums SET artwork_path = '/etc/passwd' WHERE id = 1;"

# 2. Request artwork
curl http://localhost:8765/api/albums/1/artwork
# Expected: 403 Forbidden "Access denied: path outside artwork directory"

# Test 3: Symlink attack (should be blocked)
# 1. Create symlink to sensitive file
ln -s /etc/passwd ~/.auralis/artwork/evil.jpg

# 2. Update album artwork_path
sqlite3 ~/.auralis/library.db "UPDATE albums SET artwork_path = '$HOME/.auralis/artwork/evil.jpg' WHERE id = 1;"

# 3. Request artwork
curl http://localhost:8765/api/albums/1/artwork
# Expected: 403 Forbidden "Access denied: path outside artwork directory"

# Test 4: Relative traversal (should be blocked)
# 1. Update with relative path traversal
sqlite3 ~/.auralis/library.db "UPDATE albums SET artwork_path = '$HOME/.auralis/artwork/../../../etc/passwd' WHERE id = 1;"

# 2. Request artwork
curl http://localhost:8765/api/albums/1/artwork
# Expected: 403 Forbidden "Access denied: path outside artwork directory"
```

## Security Impact

### Before Fix
- **Severity**: HIGH
- **Impact**: Arbitrary file read via path traversal
- **Attack Vector**: Database tampering + API request
- **Exploitability**: Medium (requires SQL injection or malicious update)

### After Fix
- **Severity**: NONE
- **Impact**: All file paths validated against allowed directory
- **Protection**: Defense in depth with symlink resolution
- **Monitoring**: All path traversal attempts logged

## Related Issues

- [#2078](https://github.com/matiaszanolli/Auralis/issues/2078) - SQL injection risk in fingerprint column names (enables database tampering)
- [#2236](https://github.com/matiaszanolli/Auralis/issues/2236) - Path traversal in player load endpoint (same class of vulnerability)
- [#2108](https://github.com/matiaszanolli/Auralis/issues/2108) - Hardcoded JPEG Content-Type (separate issue)

## Defense in Depth

Multiple layers of protection:

1. **Path Resolution** - Resolves symlinks and relative paths
2. **Directory Containment** - Validates path is within allowed directory
3. **Existence Check** - Ensures file exists after validation
4. **Error Segregation** - Returns 403 for security violations, 404 for missing files
5. **Audit Logging** - Logs all path traversal attempts
6. **Input Validation** - Handles edge cases (null bytes, empty paths, etc.)

## Lessons Learned

1. **Never trust database values** - Even database-backed values need validation
2. **Validate paths before serving files** - Always check containment in allowed directory
3. **Handle symlinks properly** - Resolve symlinks before validation
4. **Fail securely** - Return 403 for security violations (distinguishes from 404)
5. **Log security events** - Monitor path traversal attempts for attack detection
6. **Defense in depth** - Combine multiple validation layers

## Follow-up Actions

- [x] Fix path traversal in player load endpoint (issue #2236)
- [x] Add path validation tests
- [ ] Security audit of all FileResponse endpoints
- [ ] Add pre-commit hook to detect unsafe file serving patterns
- [ ] Fix SQL injection vulnerability (issue #2078) to prevent database tampering
- [ ] Implement Content-Security-Policy headers
- [ ] Add rate limiting to prevent brute force path scanning

## References

- OWASP: [Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory
- CWE-59: Improper Link Resolution Before File Access ('Link Following')
- Python pathlib documentation: [Path.resolve()](https://docs.python.org/3/library/pathlib.html#pathlib.Path.resolve)
- Python pathlib documentation: [Path.is_relative_to()](https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.is_relative_to)
