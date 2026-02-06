"""
Test Configuration and Fixtures

Uses PostgreSQL for testing to ensure compatibility with production database types.
Requires a running PostgreSQL instance (via Docker Compose).
"""

import pytest
import os
import tempfile
import shutil
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database, drop_database

from app.database import Base


# Test database URL - uses a separate test database
# Inside Docker: db:5432, Outside Docker: localhost:5433
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://dmarc:dmarc@db:5432/dmarc_test"
)


@pytest.fixture(scope="session")
def db_engine():
    """Create a test database engine (session-scoped for performance)"""
    # Import all models to register them with Base
    from app.models import (
        IngestedReport, DmarcRecord, DmarcReport,
        User, UserAPIKey, RefreshToken, PasswordResetToken,
        AlertHistory, AlertRule, AlertSuppression,
        GeoLocationCache, MLModel, MLPrediction, AnalyticsCache,
        AuditLog, RetentionPolicy, RetentionLog
    )
    from app.models.notification import UserNotification
    from app.models.saved_view import SavedView
    from app.services.webhook_service import WebhookEndpoint, WebhookDelivery

    # Create the test database if it doesn't exist
    if not database_exists(TEST_DATABASE_URL):
        create_database(TEST_DATABASE_URL)

    engine = create_engine(TEST_DATABASE_URL)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup - drop all tables but keep the database
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a test database session with transaction rollback"""
    connection = db_engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection
    )
    session = TestingSessionLocal()

    yield session

    # Rollback transaction to clean up test data
    session.close()
    transaction.rollback()
    connection.close()


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
def sample_xml_with_records():
    """Sample DMARC XML content with records"""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<feedback>
  <report_metadata>
    <org_name>google.com</org_name>
    <email>noreply-dmarc-support@google.com</email>
    <report_id>12345678901234567890</report_id>
    <date_range>
      <begin>1609459200</begin>
      <end>1609545600</end>
    </date_range>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
    <adkim>r</adkim>
    <aspf>r</aspf>
    <p>quarantine</p>
    <sp>none</sp>
    <pct>100</pct>
  </policy_published>
  <record>
    <row>
      <source_ip>192.168.1.1</source_ip>
      <count>10</count>
      <policy_evaluated>
        <disposition>none</disposition>
        <dkim>pass</dkim>
        <spf>pass</spf>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>example.com</header_from>
    </identifiers>
    <auth_results>
      <dkim>
        <domain>example.com</domain>
        <result>pass</result>
        <selector>selector1</selector>
      </dkim>
      <spf>
        <domain>example.com</domain>
        <result>pass</result>
        <scope>mfrom</scope>
      </spf>
    </auth_results>
  </record>
  <record>
    <row>
      <source_ip>10.0.0.1</source_ip>
      <count>5</count>
      <policy_evaluated>
        <disposition>reject</disposition>
        <dkim>fail</dkim>
        <spf>fail</spf>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>example.com</header_from>
    </identifiers>
    <auth_results>
      <dkim>
        <domain>example.com</domain>
        <result>fail</result>
      </dkim>
      <spf>
        <domain>example.com</domain>
        <result>fail</result>
      </spf>
    </auth_results>
  </record>
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


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    from app.models.user import User, UserRole
    import uuid

    user = User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$hashedpassword",  # Fake bcrypt hash
        role=UserRole.ADMIN.value,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_api_key(db_session, test_user):
    """Create a test API key"""
    from app.models.user import UserAPIKey
    import uuid
    import hashlib
    from datetime import datetime, timedelta

    # Generate a test API key
    raw_key = "test_api_key_12345"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = UserAPIKey(
        id=uuid.uuid4(),
        user_id=test_user.id,
        key_name="Test Key",
        key_prefix="test_",
        key_hash=key_hash,
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)

    # Return both the API key model and the raw key for testing
    return {"model": api_key, "raw_key": raw_key}


@pytest.fixture
def client(db_session):
    """Create a test client with database dependency override"""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield client

    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client, test_user, test_api_key):
    """Create a test client with authentication"""
    client.headers["X-API-Key"] = test_api_key["raw_key"]
    return client
