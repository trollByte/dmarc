import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import IngestedReport, DmarcReport, DmarcRecord
from pathlib import Path
import tempfile
import shutil


import os


@pytest.fixture(scope="function")
def db_engine():
    """Create a test database engine"""
    # Ensure models are imported and registered with Base
    from app.models import IngestedReport, DmarcRecord, DmarcReport
    import tempfile

    # Use a temporary file for the test database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    test_db_url = f"sqlite:///{db_path}"

    engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False}
    )

    # Create all tables from Base metadata
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a test database session"""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine
    )
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def temp_storage():
    """Create temporary storage directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_xml():
    """Sample DMARC XML content"""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<feedback>
  <report_metadata>
    <org_name>Google Inc.</org_name>
    <report_id>12345678901234567890</report_id>
    <date_range>
      <begin>1609459200</begin>
      <end>1609545600</end>
    </date_range>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
    <p>quarantine</p>
  </policy_published>
</feedback>
"""


@pytest.fixture
def sample_gzip(sample_xml):
    """Sample gzipped DMARC report"""
    import gzip
    return gzip.compress(sample_xml)


@pytest.fixture
def sample_zip(sample_xml):
    """Sample zipped DMARC report"""
    import zipfile
    import io

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.xml", sample_xml)
    return zip_buffer.getvalue()
