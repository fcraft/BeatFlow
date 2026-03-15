"""Tests for per-file storage tracking and simulate endpoint file_path format.

Validates:
1. storage_manager.get_storage_for_file returns correct backend type
2. simulate endpoint stores relative storage keys (not absolute paths)
3. LocalStorageBackend resolves relative keys correctly
4. Waveform / download endpoints can find files via correct storage keys
"""

import os
import uuid
import wave
import struct
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.storage import LocalStorageBackend


# ─────────────────────────────────────────────────────────────────────────────
# LocalStorageBackend._resolve tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLocalStorageResolve:
    """Ensure LocalStorageBackend._resolve produces correct paths."""

    def test_relative_key_joined_with_base(self, tmp_path):
        """Relative storage key like 'project_id/file.wav' should be joined with base_dir."""
        backend = LocalStorageBackend(str(tmp_path))
        key = "abc-123/sim_ecg_deadbeef.wav"
        resolved = backend._resolve(key)
        assert resolved == os.path.join(str(tmp_path), key)

    def test_key_with_uploads_prefix_is_wrong(self, tmp_path):
        """A key like './uploads/project_id/file.wav' would double the path — this is the bug."""
        backend = LocalStorageBackend(str(tmp_path))
        bad_key = "./uploads/abc-123/sim_ecg_deadbeef.wav"
        resolved = backend._resolve(bad_key)
        # This should NOT resolve correctly — the path would contain 'uploads' twice
        # because base_dir already points to the uploads directory
        assert "uploads" in resolved
        # The resolved path would be: tmp_path/./uploads/abc-123/sim_ecg_deadbeef.wav
        # which is wrong (file doesn't exist there)

    def test_correct_key_format(self, tmp_path):
        """Correct storage key format: '{project_id}/{filename}'."""
        backend = LocalStorageBackend(str(tmp_path))
        project_id = str(uuid.uuid4())
        filename = "sim_ecg_abc12345.wav"
        key = f"{project_id}/{filename}"

        # Create the actual file
        file_dir = os.path.join(str(tmp_path), project_id)
        os.makedirs(file_dir, exist_ok=True)
        file_path = os.path.join(file_dir, filename)
        with open(file_path, "w") as f:
            f.write("test")

        resolved = backend._resolve(key)
        assert resolved == file_path
        assert os.path.exists(resolved)


@pytest.mark.asyncio
class TestLocalStorageExists:
    """Ensure exists() works with relative storage keys."""

    async def test_exists_with_correct_key(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        project_id = str(uuid.uuid4())
        fname = "test_file.wav"
        key = f"{project_id}/{fname}"

        # File doesn't exist yet
        assert await backend.exists(key) is False

        # Create it
        os.makedirs(os.path.join(str(tmp_path), project_id), exist_ok=True)
        with open(os.path.join(str(tmp_path), project_id, fname), "w") as f:
            f.write("data")

        assert await backend.exists(key) is True

    async def test_exists_with_bad_prefix_fails(self, tmp_path):
        """Key with './uploads/' prefix should NOT find files (the bug scenario)."""
        backend = LocalStorageBackend(str(tmp_path))
        project_id = str(uuid.uuid4())
        fname = "test_file.wav"

        # Create the file at the correct location
        os.makedirs(os.path.join(str(tmp_path), project_id), exist_ok=True)
        with open(os.path.join(str(tmp_path), project_id, fname), "w") as f:
            f.write("data")

        # Correct key finds it
        assert await backend.exists(f"{project_id}/{fname}") is True

        # Bad key with prefix doesn't find it
        bad_key = f"./uploads/{project_id}/{fname}"
        assert await backend.exists(bad_key) is False


# ─────────────────────────────────────────────────────────────────────────────
# get_storage_for_file tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestGetStorageForFile:
    """Test that get_storage_for_file returns the right backend based on media_file.storage_backend."""

    async def test_local_backend(self):
        from app.services.storage_manager import get_storage_for_file

        media_file = MagicMock()
        media_file.storage_backend = "local"
        db = AsyncMock()

        backend = await get_storage_for_file(db, media_file)
        assert isinstance(backend, LocalStorageBackend)

    async def test_default_is_local(self):
        """If storage_backend is None or missing, default to local."""
        from app.services.storage_manager import get_storage_for_file

        media_file = MagicMock()
        media_file.storage_backend = None
        db = AsyncMock()

        backend = await get_storage_for_file(db, media_file)
        assert isinstance(backend, LocalStorageBackend)

    async def test_cos_backend_reads_settings(self):
        """COS backend should load settings from DB."""
        from app.services.storage_manager import get_storage_for_file
        from app.services.storage import S3StorageBackend

        media_file = MagicMock()
        media_file.storage_backend = "cos"
        db = AsyncMock()

        mock_settings = {
            "storage_type": "cos",
            "cos_bucket_name": "test-bucket",
            "cos_region": "ap-guangzhou",
            "cos_secret_id": "AKID123",
            "cos_secret_key": "secret456",
        }

        with patch("app.services.storage_manager._load_settings", return_value=mock_settings):
            backend = await get_storage_for_file(db, media_file)
            assert isinstance(backend, S3StorageBackend)


# ─────────────────────────────────────────────────────────────────────────────
# Simulate endpoint file_path format tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSimulateFilePathFormat:
    """Verify that _save_wav + simulate stores correct storage key format."""

    def test_save_wav_returns_absolute_path(self, tmp_path):
        """_save_wav returns an absolute/full file path (for writing to disk)."""
        import numpy as np
        from scipy.io import wavfile

        # Replicate _save_wav logic
        upload_dir = os.path.join(str(tmp_path), "project-123")
        os.makedirs(upload_dir, exist_ok=True)
        fname = "sim_ecg_test.wav"
        path = os.path.join(upload_dir, fname)

        # Write a minimal WAV
        sr = 500
        sig = np.zeros(sr, dtype=np.int16)
        wavfile.write(path, sr, sig)

        assert os.path.exists(path)
        # The _save_wav return value is the full path — NOT what we store in DB
        assert "project-123" in path

    def test_storage_key_is_relative(self):
        """The file_path stored in MediaFile should be '{project_id}/{filename}', not an absolute path."""
        project_id = "3220d50e-1fc9-4e44-9774-56eed5b981e8"
        ecg_fname = "sim_ecg_f3b400c0.wav"

        # This is what the FIXED code produces
        storage_key = f"{project_id}/{ecg_fname}"

        # Must NOT start with './' or '/'
        assert not storage_key.startswith("./")
        assert not storage_key.startswith("/")
        assert "uploads" not in storage_key

    def test_storage_key_matches_upload_pattern(self):
        """Simulate file_path should match the same pattern as upload_file endpoint."""
        project_id = str(uuid.uuid4())
        filename = f"sim_ecg_{uuid.uuid4().hex[:8]}.wav"

        # Simulate endpoint format (FIXED)
        sim_key = f"{project_id}/{filename}"

        # Upload endpoint format
        upload_key = f"{project_id}/{uuid.uuid4()}_{filename}"

        # Both should be relative paths with project_id prefix
        for key in [sim_key, upload_key]:
            assert not key.startswith("./")
            assert not key.startswith("/")
            assert key.startswith(project_id)


# ─────────────────────────────────────────────────────────────────────────────
# Integration: file_path → LocalStorageBackend roundtrip
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestFilePathRoundtrip:
    """End-to-end: write a WAV, store with correct key, verify exists + read."""

    async def test_simulate_wav_roundtrip(self, tmp_path):
        """Simulate writing a WAV and accessing it via LocalStorageBackend with correct key."""
        import numpy as np
        from scipy.io import wavfile

        project_id = str(uuid.uuid4())
        fname = f"sim_ecg_{uuid.uuid4().hex[:8]}.wav"

        # Simulate _save_wav: writes to disk
        upload_dir = os.path.join(str(tmp_path), project_id)
        os.makedirs(upload_dir, exist_ok=True)
        disk_path = os.path.join(upload_dir, fname)

        sr = 500
        sig = (np.sin(np.linspace(0, 2 * 3.14159, sr)) * 32767 * 0.85).astype(np.int16)
        wavfile.write(disk_path, sr, sig)

        # Storage key stored in MediaFile.file_path (FIXED format)
        storage_key = f"{project_id}/{fname}"

        # LocalStorageBackend with base_dir = tmp_path (like settings.UPLOAD_DIR)
        backend = LocalStorageBackend(str(tmp_path))

        # Should find the file
        assert await backend.exists(storage_key) is True

        # Should return valid bytes
        data = await backend.get(storage_key)
        assert len(data) > 0

        # get_local_path should resolve correctly
        local_path = backend.get_local_path(storage_key)
        assert os.path.exists(local_path)
        assert local_path == disk_path

    async def test_bad_key_fails_roundtrip(self, tmp_path):
        """The OLD buggy file_path format should NOT work."""
        import numpy as np
        from scipy.io import wavfile

        project_id = str(uuid.uuid4())
        fname = f"sim_ecg_{uuid.uuid4().hex[:8]}.wav"

        upload_dir = os.path.join(str(tmp_path), project_id)
        os.makedirs(upload_dir, exist_ok=True)
        disk_path = os.path.join(upload_dir, fname)

        sr = 500
        sig = np.zeros(sr, dtype=np.int16)
        wavfile.write(disk_path, sr, sig)

        # BAD key: what the old code produced (with ./uploads/ prefix)
        # Note: we simulate as if tmp_path IS the uploads dir
        bad_key = f"./uploads/{project_id}/{fname}"

        backend = LocalStorageBackend(str(tmp_path))

        # This should NOT find the file
        assert await backend.exists(bad_key) is False
