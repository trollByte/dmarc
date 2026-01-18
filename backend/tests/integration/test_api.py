"""Integration tests for API endpoints"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from app.main import app
from app.models import DmarcReport, DmarcRecord
from app.database import get_db


@pytest.fixture
def client(db_session):
    """Create test client with database dependency override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seed_data(db_session):
    """Seed database with test data"""
    # Create reports for example.com
    report1 = DmarcReport(
        report_id="report1",
        org_name="Google",
        email="noreply@google.com",
        domain="example.com",
        date_begin=datetime(2024, 1, 1, 0, 0, 0),
        date_end=datetime(2024, 1, 1, 23, 59, 59),
        p="quarantine",
        sp="none",
        pct=100,
        adkim="r",
        aspf="r"
    )
    db_session.add(report1)
    db_session.flush()

    # Add records for report1
    records1 = [
        DmarcRecord(
            report_id=report1.id,
            source_ip="192.0.2.1",
            count=10,
            disposition="none",
            dkim="pass",
            spf="pass",
            dkim_result="pass",
            spf_result="pass",
            header_from="example.com"
        ),
        DmarcRecord(
            report_id=report1.id,
            source_ip="198.51.100.42",
            count=5,
            disposition="quarantine",
            dkim="fail",
            spf="fail",
            dkim_result="fail",
            spf_result="fail",
            header_from="example.com"
        ),
        DmarcRecord(
            report_id=report1.id,
            source_ip="203.0.113.1",
            count=3,
            disposition="none",
            dkim="pass",
            spf="fail",
            dkim_result="pass",
            spf_result="fail",
            header_from="example.com"
        )
    ]
    for record in records1:
        db_session.add(record)

    # Create second report for example.com
    report2 = DmarcReport(
        report_id="report2",
        org_name="Yahoo",
        email="dmarc@yahoo.com",
        domain="example.com",
        date_begin=datetime(2024, 1, 2, 0, 0, 0),
        date_end=datetime(2024, 1, 2, 23, 59, 59),
        p="reject",
        pct=100
    )
    db_session.add(report2)
    db_session.flush()

    # Add records for report2
    records2 = [
        DmarcRecord(
            report_id=report2.id,
            source_ip="192.0.2.1",
            count=20,
            disposition="none",
            dkim="pass",
            spf="pass",
            dkim_result="pass",
            spf_result="pass",
            header_from="example.com"
        ),
        DmarcRecord(
            report_id=report2.id,
            source_ip="198.51.100.42",
            count=2,
            disposition="reject",
            dkim="fail",
            spf="pass",
            dkim_result="fail",
            spf_result="pass",
            header_from="example.com"
        )
    ]
    for record in records2:
        db_session.add(record)

    # Create report for other.com
    report3 = DmarcReport(
        report_id="report3",
        org_name="Microsoft",
        email="dmarc@microsoft.com",
        domain="other.com",
        date_begin=datetime(2024, 1, 3, 0, 0, 0),
        date_end=datetime(2024, 1, 3, 23, 59, 59),
        p="none",
        pct=100
    )
    db_session.add(report3)
    db_session.flush()

    # Add records for report3
    records3 = [
        DmarcRecord(
            report_id=report3.id,
            source_ip="203.0.113.50",
            count=15,
            disposition="none",
            dkim="pass",
            spf="pass",
            dkim_result="pass",
            spf_result="pass",
            header_from="other.com"
        )
    ]
    for record in records3:
        db_session.add(record)

    db_session.commit()


class TestHealthCheck:
    """Test health check endpoint"""

    def test_healthz(self, client):
        """Test /api/healthz endpoint"""
        response = client.get("/api/healthz")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["healthy", "unhealthy"]
        assert data["service"] == "DMARC Report Processor API"
        assert data["database"] in ["connected", "disconnected"]


class TestDomains:
    """Test domains endpoint"""

    def test_list_domains(self, client, seed_data):
        """Test GET /api/domains"""
        response = client.get("/api/domains")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["domains"]) == 2

        # Check domains are sorted alphabetically
        assert data["domains"][0]["domain"] == "example.com"
        assert data["domains"][1]["domain"] == "other.com"

        # Check example.com stats
        example_domain = data["domains"][0]
        assert example_domain["report_count"] == 2
        assert example_domain["earliest_report"] is not None
        assert example_domain["latest_report"] is not None

    def test_list_domains_empty(self, client, db_session):
        """Test GET /api/domains with no data"""
        response = client.get("/api/domains")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert len(data["domains"]) == 0


class TestReports:
    """Test reports endpoint"""

    def test_list_reports(self, client, seed_data):
        """Test GET /api/reports"""
        response = client.get("/api/reports")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["reports"]) == 3

        # Reports should be sorted by date_end descending
        assert data["reports"][0]["report_id"] == "report3"
        assert data["reports"][1]["report_id"] == "report2"
        assert data["reports"][2]["report_id"] == "report1"

    def test_list_reports_filter_domain(self, client, seed_data):
        """Test GET /api/reports with domain filter"""
        response = client.get("/api/reports?domain=example.com")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["reports"]) == 2

        # All reports should be for example.com
        for report in data["reports"]:
            assert report["domain"] == "example.com"

    def test_list_reports_filter_dates(self, client, seed_data):
        """Test GET /api/reports with date filters"""
        response = client.get("/api/reports?start=2024-01-02T00:00:00&end=2024-01-02T23:59:59")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] >= 1

        # Check that reports are within date range
        for report in data["reports"]:
            date_begin = datetime.fromisoformat(report["date_begin"].replace('Z', '+00:00'))
            assert date_begin >= datetime(2024, 1, 2, 0, 0, 0)

    def test_list_reports_pagination(self, client, seed_data):
        """Test GET /api/reports with pagination"""
        # Get first page
        response = client.get("/api/reports?page=1&page_size=2")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["reports"]) == 2

        # Get second page
        response = client.get("/api/reports?page=2&page_size=2")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 2
        assert len(data["reports"]) == 1

    def test_list_reports_computed_fields(self, client, seed_data):
        """Test that reports include computed fields"""
        response = client.get("/api/reports?domain=example.com")
        assert response.status_code == 200

        data = response.json()
        report1_data = next(r for r in data["reports"] if r["report_id"] == "report1")

        assert report1_data["record_count"] == 3
        assert report1_data["total_messages"] == 18  # 10 + 5 + 3


class TestRollupSummary:
    """Test rollup summary endpoint"""

    def test_rollup_summary_all(self, client, seed_data):
        """Test GET /api/rollup/summary for all data"""
        response = client.get("/api/rollup/summary")
        assert response.status_code == 200

        data = response.json()
        assert data["total_reports"] == 3
        assert data["total_messages"] == 55  # 10+5+3+20+2+15
        assert data["pass_count"] == 45  # 10+20+15 (all with both pass)
        assert data["fail_count"] == 10  # 5+3+2 (not both pass)
        assert data["pass_percentage"] > 0
        assert data["fail_percentage"] > 0
        assert data["disposition_none"] > 0

    def test_rollup_summary_filter_domain(self, client, seed_data):
        """Test GET /api/rollup/summary with domain filter"""
        response = client.get("/api/rollup/summary?domain=example.com")
        assert response.status_code == 200

        data = response.json()
        assert data["total_reports"] == 2
        assert data["total_messages"] == 40  # 10+5+3+20+2
        assert data["pass_count"] == 30  # 10+20
        assert data["fail_count"] == 10  # 5+3+2

    def test_rollup_summary_empty(self, client, db_session):
        """Test GET /api/rollup/summary with no data"""
        response = client.get("/api/rollup/summary")
        assert response.status_code == 200

        data = response.json()
        assert data["total_reports"] == 0
        assert data["total_messages"] == 0
        assert data["pass_count"] == 0
        assert data["fail_count"] == 0


class TestRollupSources:
    """Test rollup sources endpoint"""

    def test_rollup_sources(self, client, seed_data):
        """Test GET /api/rollup/sources"""
        response = client.get("/api/rollup/sources")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 4  # 4 unique source IPs across all reports
        assert len(data["sources"]) == 4

        # Sources should be sorted by total_count descending
        assert data["sources"][0]["source_ip"] == "192.0.2.1"
        assert data["sources"][0]["total_count"] == 30  # 10+20

    def test_rollup_sources_filter_domain(self, client, seed_data):
        """Test GET /api/rollup/sources with domain filter"""
        response = client.get("/api/rollup/sources?domain=example.com")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 3  # Three source IPs for example.com

    def test_rollup_sources_pagination(self, client, seed_data):
        """Test GET /api/rollup/sources with pagination"""
        response = client.get("/api/rollup/sources?page=1&page_size=2")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 4  # 4 unique source IPs total
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["sources"]) == 2

    def test_rollup_sources_stats(self, client, seed_data):
        """Test source IP statistics calculations"""
        response = client.get("/api/rollup/sources")
        assert response.status_code == 200

        data = response.json()
        source_192 = next(s for s in data["sources"] if s["source_ip"] == "192.0.2.1")

        assert source_192["pass_count"] == 30  # All records pass
        assert source_192["fail_count"] == 0
        assert source_192["pass_percentage"] == 100.0


class TestRollupAlignment:
    """Test rollup alignment endpoint"""

    def test_rollup_alignment(self, client, seed_data):
        """Test GET /api/rollup/alignment"""
        response = client.get("/api/rollup/alignment")
        assert response.status_code == 200

        data = response.json()
        assert data["total_messages"] == 55
        assert data["spf_pass"] > 0
        assert data["dkim_pass"] > 0
        assert data["both_pass"] == 45  # 10+20+15
        assert data["both_pass_percentage"] > 0

    def test_rollup_alignment_filter_domain(self, client, seed_data):
        """Test GET /api/rollup/alignment with domain filter"""
        response = client.get("/api/rollup/alignment?domain=example.com")
        assert response.status_code == 200

        data = response.json()
        assert data["total_messages"] == 40

    def test_rollup_alignment_calculations(self, client, seed_data):
        """Test alignment percentage calculations"""
        response = client.get("/api/rollup/alignment?domain=example.com")
        assert response.status_code == 200

        data = response.json()
        # report1: 10 pass/pass, 5 fail/fail, 3 fail/pass (DKIM pass)
        # report2: 20 pass/pass, 2 pass/fail (SPF pass)
        # Total: 40 messages
        # SPF pass: 10 + 20 + 2 = 32
        # DKIM pass: 10 + 3 + 20 = 33
        # Both pass: 10 + 20 = 30

        assert data["spf_pass"] == 32
        assert data["dkim_pass"] == 33
        assert data["both_pass"] == 30
        assert data["both_pass_percentage"] == 75.0  # 30/40 = 75%

    def test_rollup_alignment_empty(self, client, db_session):
        """Test GET /api/rollup/alignment with no data"""
        response = client.get("/api/rollup/alignment")
        assert response.status_code == 200

        data = response.json()
        assert data["total_messages"] == 0
        assert data["spf_pass"] == 0
        assert data["dkim_pass"] == 0


class TestUploadEndpoint:
    """Test bulk upload endpoint"""

    def test_upload_single_xml_file(self, client, db_session, sample_xml):
        """Test uploading single XML file"""
        from io import BytesIO

        files = [
            ("files", ("report.xml", BytesIO(sample_xml), "application/xml"))
        ]

        response = client.post("/api/upload", files=files)
        assert response.status_code == 200

        data = response.json()
        assert data["total_files"] == 1
        assert data["uploaded"] == 1
        assert data["duplicates"] == 0
        assert data["errors"] == 0
        assert data["invalid_files"] == 0
        assert data["auto_processed"] is True
        assert len(data["files"]) == 1

        file_detail = data["files"][0]
        assert file_detail["filename"] == "report.xml"
        assert file_detail["status"] == "uploaded"
        assert file_detail["content_hash"] is not None

    def test_upload_gzip_file(self, client, db_session, sample_gzip):
        """Test uploading gzip file"""
        from io import BytesIO

        files = [
            ("files", ("report.xml.gz", BytesIO(sample_gzip), "application/gzip"))
        ]

        response = client.post("/api/upload", files=files)
        assert response.status_code == 200

        data = response.json()
        assert data["uploaded"] == 1
        assert data["files"][0]["status"] == "uploaded"

    def test_upload_zip_file(self, client, db_session, sample_zip):
        """Test uploading zip file"""
        from io import BytesIO

        files = [
            ("files", ("report.zip", BytesIO(sample_zip), "application/zip"))
        ]

        response = client.post("/api/upload", files=files)
        assert response.status_code == 200

        data = response.json()
        assert data["uploaded"] == 1
        assert data["files"][0]["status"] == "uploaded"

    def test_upload_multiple_files(self, client, db_session, sample_xml, sample_gzip):
        """Test uploading multiple files"""
        from io import BytesIO

        files = [
            ("files", ("report1.xml", BytesIO(sample_xml), "application/xml")),
            ("files", ("report2.xml.gz", BytesIO(sample_gzip), "application/gzip"))
        ]

        response = client.post("/api/upload", files=files)
        assert response.status_code == 200

        data = response.json()
        assert data["total_files"] == 2
        assert data["uploaded"] == 2
        assert len(data["files"]) == 2

    def test_upload_duplicate_file(self, client, db_session, sample_xml):
        """Test uploading same file twice"""
        from io import BytesIO

        files = [
            ("files", ("report.xml", BytesIO(sample_xml), "application/xml"))
        ]

        # Upload first time
        response1 = client.post("/api/upload", files=files)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["uploaded"] == 1

        # Upload second time (duplicate)
        response2 = client.post("/api/upload", files=files)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["total_files"] == 1
        assert data2["duplicates"] == 1
        assert data2["uploaded"] == 0
        assert data2["files"][0]["status"] == "duplicate"

    def test_upload_invalid_extension(self, client, db_session):
        """Test uploading file with invalid extension"""
        from io import BytesIO

        files = [
            ("files", ("report.txt", BytesIO(b"invalid content"), "text/plain"))
        ]

        response = client.post("/api/upload", files=files)
        assert response.status_code == 200

        data = response.json()
        assert data["total_files"] == 1
        assert data["invalid_files"] == 1
        assert data["uploaded"] == 0
        assert data["files"][0]["status"] == "invalid"
        assert "Invalid file type" in data["files"][0]["error_message"]

    def test_upload_without_auto_process(self, client, db_session, sample_xml):
        """Test uploading without auto-processing"""
        from io import BytesIO

        files = [
            ("files", ("report.xml", BytesIO(sample_xml), "application/xml"))
        ]

        response = client.post("/api/upload?auto_process=false", files=files)
        assert response.status_code == 200

        data = response.json()
        assert data["uploaded"] == 1
        assert data["auto_processed"] is False
        assert data["reports_processed"] is None

    def test_upload_no_files(self, client, db_session):
        """Test upload with no files"""
        response = client.post("/api/upload", files=[])
        assert response.status_code == 422  # Validation error


class TestAuthentication:
    """Test API key authentication"""

    def test_upload_without_api_key(self, client, db_session, monkeypatch):
        """Test upload without API key when required"""
        from app.config import Settings

        # Mock settings to require API key
        def mock_get_settings():
            settings = Settings()
            settings.require_api_key = True
            settings.api_keys = "test-key-1,test-key-2"
            return settings

        monkeypatch.setattr("app.middleware.auth.get_settings", mock_get_settings)

        from io import BytesIO
        files = [("files", ("test.xml", BytesIO(b"<xml/>"), "application/xml"))]

        response = client.post("/api/upload", files=files)
        assert response.status_code == 401

    def test_upload_with_invalid_api_key(self, client, db_session, monkeypatch):
        """Test upload with invalid API key"""
        from app.config import Settings

        # Mock settings to require API key
        def mock_get_settings():
            settings = Settings()
            settings.require_api_key = True
            settings.api_keys = "test-key-1,test-key-2"
            return settings

        monkeypatch.setattr("app.middleware.auth.get_settings", mock_get_settings)

        from io import BytesIO
        files = [("files", ("test.xml", BytesIO(b"<xml/>"), "application/xml"))]
        headers = {"X-API-Key": "invalid-key"}

        response = client.post("/api/upload", files=files, headers=headers)
        assert response.status_code == 403

    def test_upload_with_valid_api_key(self, client, db_session, sample_xml, monkeypatch):
        """Test upload with valid API key"""
        from app.config import Settings

        # Mock settings to require API key
        def mock_get_settings():
            settings = Settings()
            settings.require_api_key = True
            settings.api_keys = "test-key-1,test-key-2"
            return settings

        monkeypatch.setattr("app.middleware.auth.get_settings", mock_get_settings)

        from io import BytesIO
        files = [("files", ("test.xml", BytesIO(sample_xml), "application/xml"))]
        headers = {"X-API-Key": "test-key-1"}

        response = client.post("/api/upload", files=files, headers=headers)
        assert response.status_code == 200

    def test_trigger_endpoints_require_auth(self, client, db_session, monkeypatch):
        """Test that trigger endpoints require authentication"""
        from app.config import Settings

        # Mock settings to require API key
        def mock_get_settings():
            settings = Settings()
            settings.require_api_key = True
            settings.api_keys = "test-key-1"
            return settings

        monkeypatch.setattr("app.middleware.auth.get_settings", mock_get_settings)

        # Test email ingestion trigger
        response = client.post("/api/ingest/trigger")
        assert response.status_code == 401

        # Test processing trigger
        response = client.post("/api/process/trigger")
        assert response.status_code == 401
