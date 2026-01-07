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
