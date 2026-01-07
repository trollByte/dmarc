import pytest
from app.services.storage import StorageService


class TestStorageService:
    """Test storage service functionality"""

    def test_compute_hash(self, temp_storage):
        """Test hash computation is deterministic"""
        storage = StorageService(temp_storage)

        content1 = b"test content"
        content2 = b"test content"
        content3 = b"different content"

        hash1 = storage.compute_hash(content1)
        hash2 = storage.compute_hash(content2)
        hash3 = storage.compute_hash(content3)

        # Same content should produce same hash
        assert hash1 == hash2

        # Different content should produce different hash
        assert hash1 != hash3

        # Hash should be 64 characters (SHA256 hex)
        assert len(hash1) == 64

    def test_save_file(self, temp_storage, sample_xml):
        """Test file saving"""
        storage = StorageService(temp_storage)

        storage_path, content_hash, file_size = storage.save_file(
            sample_xml,
            "report.xml"
        )

        # Verify return values
        assert storage_path
        assert content_hash
        assert file_size == len(sample_xml)

        # Verify file exists
        assert storage.file_exists(storage_path)

        # Verify content can be retrieved
        retrieved = storage.get_file(storage_path)
        assert retrieved == sample_xml

    def test_save_duplicate_file(self, temp_storage, sample_xml):
        """Test saving same file twice produces same hash"""
        storage = StorageService(temp_storage)

        path1, hash1, size1 = storage.save_file(sample_xml, "report1.xml")
        path2, hash2, size2 = storage.save_file(sample_xml, "report2.xml")

        # Same content should produce same hash
        assert hash1 == hash2

        # Paths will be different (different filenames)
        assert path1 != path2

        # Both files should exist
        assert storage.file_exists(path1)
        assert storage.file_exists(path2)

    def test_get_nonexistent_file(self, temp_storage):
        """Test retrieving nonexistent file raises error"""
        storage = StorageService(temp_storage)

        with pytest.raises(FileNotFoundError):
            storage.get_file("nonexistent/path.xml")

    def test_storage_path_structure(self, temp_storage, sample_xml):
        """Test storage path follows expected structure"""
        storage = StorageService(temp_storage)

        storage_path, _, _ = storage.save_file(sample_xml, "test.xml")

        # Path should contain year/month/day structure
        parts = storage_path.split('/')
        assert len(parts) >= 4  # YYYY/MM/DD/hash_prefix/filename

        # First part should be year (4 digits)
        assert len(parts[0]) == 4
        assert parts[0].isdigit()

        # Filename should be preserved
        assert parts[-1] == "test.xml"
