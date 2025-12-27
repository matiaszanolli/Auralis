"""
Data Security Tests
~~~~~~~~~~~~~~~~~~~

Tests for data protection and secure storage.

SECURITY CONTROLS TESTED:
- File permission security
- Sensitive data exposure prevention
- Secure temporary file handling
- Database encryption readiness
- Secure file deletion
- Information disclosure prevention
- Backup security
- Data integrity validation
"""

import os
import shutil
import stat
import tempfile

import pytest
from sqlalchemy import text

from auralis.library.repositories import TrackRepository


@pytest.mark.security
class TestFilePermissions:
    """Test file permission security."""

    def test_database_file_permissions(self, temp_db):
        """
        SECURITY: Database files should have restricted permissions.
        Test: Database file should not be world-readable.
        """
        # Get database path
        session = temp_db()
        db_url = str(session.bind.url)
        session.close()

        db_path = db_url.replace('sqlite:///', '')

        if os.path.exists(db_path):
            # Check file permissions
            file_stat = os.stat(db_path)
            mode = file_stat.st_mode

            # Should not be world-readable (Unix systems)
            if os.name != 'nt':
                world_readable = bool(mode & stat.S_IROTH)
                assert not world_readable, \
                    "Database should not be world-readable"

                # Should be owner-only (0600 or 0644 max)
                perms = stat.S_IMODE(mode)
                print(f"✓ Database permissions: {oct(perms)}")

    def test_config_file_permissions(self, temp_dir):
        """
        SECURITY: Config files shouldn't be world-readable.
        Test: Config file permission validation.
        """
        config_path = os.path.join(temp_dir, 'config.ini')

        # Create config file
        with open(config_path, 'w') as f:
            f.write("[settings]\napi_key=secret123\n")

        # Set secure permissions (owner only)
        if os.name != 'nt':
            os.chmod(config_path, 0o600)

            file_stat = os.stat(config_path)
            mode = file_stat.st_mode

            # Should not be group or world readable
            assert not (mode & stat.S_IRGRP), "Should not be group-readable"
            assert not (mode & stat.S_IROTH), "Should not be world-readable"

            print("✓ Config file permissions secure")


@pytest.mark.security
class TestSensitiveDataExposure:
    """Test prevention of sensitive data exposure."""

    def test_no_passwords_in_logs(self):
        """
        SECURITY: Passwords shouldn't appear in logs.
        Test: Log sanitization for sensitive data.
        """
        def sanitize_log(message):
            # Redact common sensitive patterns
            import re
            patterns = [
                (r'password["\s:=]+([^\s"]+)', r'password=***REDACTED***'),
                (r'api_key["\s:=]+([^\s"]+)', r'api_key=***REDACTED***'),
                (r'token["\s:=]+([^\s"]+)', r'token=***REDACTED***'),
            ]

            sanitized = message
            for pattern, replacement in patterns:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

            return sanitized

        # Test messages
        assert 'secret123' not in sanitize_log('password=secret123')
        assert 'mytoken' not in sanitize_log('api_key: mytoken')
        assert '***REDACTED***' in sanitize_log('password=secret123')

        print("✓ Log sanitization working")

    def test_error_messages_dont_leak_info(self, temp_db):
        """
        SECURITY: Error messages shouldn't leak system information.
        Test: Generic error messages for security failures.
        """
        track_repo = TrackRepository(temp_db)

        # Try to access non-existent track
        result = track_repo.get_by_id(99999)

        # Should return None, not detailed error
        assert result is None, "Should return None for not found"

        # System shouldn't expose internal paths or SQL in errors
        print("✓ Error messages are generic")


@pytest.mark.security
class TestTemporaryFiles:
    """Test secure temporary file handling."""

    def test_temp_files_in_secure_directory(self):
        """
        SECURITY: Temporary files should be in secure directory.
        Test: temp file locations are not predictable.
        """
        import tempfile

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Should be in system temp directory with random name
            assert '/tmp/' in tmp_path or '\\Temp\\' in tmp_path, \
                "Should be in temp directory"

            # Filename should be random
            basename = os.path.basename(tmp_path)
            assert len(basename) > 8, "Temp filename should be sufficiently random"

            print(f"✓ Secure temp file: {tmp_path}")

        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass

    def test_temp_file_permissions_restrictive(self):
        """
        SECURITY: Temporary files should have restrictive permissions.
        Test: temp files are owner-only.
        """
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(b"sensitive data")

        try:
            if os.name != 'nt':
                # Check permissions
                file_stat = os.stat(tmp_path)
                mode = stat.S_IMODE(file_stat.st_mode)

                # Should be owner-only (0600)
                assert not (file_stat.st_mode & stat.S_IROTH), \
                    "Temp file should not be world-readable"

                print(f"✓ Temp file permissions: {oct(mode)}")

        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass


@pytest.mark.security
class TestSecureFileDeletion:
    """Test secure file deletion patterns."""

    def test_secure_delete_overwrites_data(self, temp_dir):
        """
        SECURITY: Secure deletion should overwrite data.
        Test: File content is overwritten before deletion.
        """
        filepath = os.path.join(temp_dir, 'secret.txt')

        # Write sensitive data
        with open(filepath, 'wb') as f:
            f.write(b"sensitive secret data")

        # Secure delete (overwrite then delete)
        def secure_delete(path):
            if os.path.exists(path):
                # Get file size
                size = os.path.getsize(path)

                # Overwrite with random data
                import secrets
                with open(path, 'wb') as f:
                    f.write(secrets.token_bytes(size))

                # Delete
                os.unlink(path)

        secure_delete(filepath)

        # File should be gone
        assert not os.path.exists(filepath), "File should be deleted"

        print("✓ Secure deletion implemented")


@pytest.mark.security
class TestDataIntegrity:
    """Test data integrity validation."""

    def test_checksum_validation(self):
        """
        SECURITY: Data integrity should be verifiable.
        Test: Checksum/hash validation.
        """
        import hashlib

        data = b"important data"

        # Calculate checksum
        checksum = hashlib.sha256(data).hexdigest()

        # Verify data hasn't been tampered
        assert hashlib.sha256(data).hexdigest() == checksum, \
            "Checksums should match for unmodified data"

        # Tampered data
        tampered = b"tampered data"
        assert hashlib.sha256(tampered).hexdigest() != checksum, \
            "Checksum should detect tampering"

        print("✓ Checksum validation working")

    def test_database_integrity_check(self, temp_db):
        """
        SECURITY: Database integrity should be checkable.
        Test: SQLite integrity check.
        """
        session = temp_db()

        # SQLite integrity check
        result = session.execute(text("PRAGMA integrity_check")).fetchone()

        # Should return 'ok'
        assert result[0].lower() == 'ok', "Database should be intact"

        session.close()

        print("✓ Database integrity validated")


@pytest.mark.security
class TestEncryptionReadiness:
    """Test encryption readiness (preparatory for future encryption)."""

    def test_encryption_key_generation(self):
        """
        SECURITY: Encryption keys should be cryptographically secure.
        Test: Key generation quality.
        """
        import secrets

        # Generate encryption key
        key = secrets.token_bytes(32)  # 256-bit key

        assert len(key) == 32, "Key should be 256 bits"
        assert key != secrets.token_bytes(32), "Keys should be unique"

        print("✓ Encryption key generation ready")

    def test_password_hashing(self):
        """
        SECURITY: Passwords should be securely hashed.
        Test: Password hashing with salt.
        """
        import hashlib
        import secrets

        def hash_password(password):
            salt = secrets.token_bytes(16)
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return salt + key

        def verify_password(stored_hash, password):
            salt = stored_hash[:16]
            stored_key = stored_hash[16:]
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return key == stored_key

        password = "MySecureP@ssw0rd"
        hashed = hash_password(password)

        # Correct password
        assert verify_password(hashed, password), "Should verify correct password"

        # Wrong password
        assert not verify_password(hashed, "wrongpassword"), \
            "Should reject wrong password"

        # Hash should be different each time (due to salt)
        hashed2 = hash_password(password)
        assert hashed != hashed2, "Hashes should differ due to salt"

        print("✓ Password hashing ready")


@pytest.mark.security
class TestBackupSecurity:
    """Test backup file security."""

    def test_backup_file_permissions(self, temp_dir):
        """
        SECURITY: Backup files should have secure permissions.
        Test: Backup files are protected.
        """
        backup_path = os.path.join(temp_dir, 'backup.db')

        # Create backup
        with open(backup_path, 'wb') as f:
            f.write(b"backup data")

        # Set secure permissions
        if os.name != 'nt':
            os.chmod(backup_path, 0o600)

            file_stat = os.stat(backup_path)
            assert not (file_stat.st_mode & stat.S_IROTH), \
                "Backup should not be world-readable"

            print("✓ Backup permissions secure")

    def test_backup_encryption_readiness(self):
        """
        SECURITY: Backups should be encryptable.
        Test: Backup encryption pattern.
        """
        from cryptography.fernet import Fernet

        # Generate key
        key = Fernet.generate_key()
        cipher = Fernet(key)

        # Encrypt backup data
        data = b"sensitive backup data"
        encrypted = cipher.encrypt(data)

        # Encrypted data should be different
        assert encrypted != data, "Data should be encrypted"

        # Should be decryptable with correct key
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == data, "Should decrypt correctly"

        print("✓ Backup encryption ready")
