"""Unit tests for TLSRPTService (tls_rpt_service.py)"""
import pytest
import json
import gzip
import hashlib
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from app.services.tls_rpt_service import (
    TLSRPTService,
    TLSReport,
    TLSFailureSummary,
    TLSRPTSummary,
    TLSPolicy,
    FailureDetail,
    PolicyType,
    ResultType,
)


def _make_rfc8460_report(
    org_name="Example Corp",
    report_id="rpt-2024-001",
    contact="mailto:tls-reports@example.com",
    start_datetime="2024-01-15T00:00:00Z",
    end_datetime="2024-01-16T00:00:00Z",
    policy_type="sts",
    policy_domain="example.com",
    policy_string=None,
    mx_host="mx.example.com",
    total_success=1000,
    total_failure=5,
    failure_details=None,
):
    """Build a minimal RFC 8460 TLS-RPT JSON report."""
    if policy_string is None:
        policy_string = ["mode: enforce", "max_age: 86400"]
    if failure_details is None:
        failure_details = [
            {
                "result-type": "certificate-expired",
                "sending-mta-ip": "203.0.113.1",
                "receiving-mx-hostname": mx_host,
                "receiving-ip": "198.51.100.1",
                "failed-session-count": total_failure,
                "additional-information": "cert expired 2024-01-10",
                "failure-reason-code": "X509_V_ERR_CERT_HAS_EXPIRED",
            }
        ]

    return {
        "organization-name": org_name,
        "date-range": {
            "start-datetime": start_datetime,
            "end-datetime": end_datetime,
        },
        "contact-info": contact,
        "report-id": report_id,
        "policies": [
            {
                "policy": {
                    "policy-type": policy_type,
                    "policy-string": policy_string,
                    "policy-domain": policy_domain,
                    "mx-host": mx_host,
                },
                "summary": {
                    "total-successful-session-count": total_success,
                    "total-failure-session-count": total_failure,
                },
                "failure-details": failure_details,
            }
        ],
    }


def _report_bytes(report_dict):
    """Encode a report dict to JSON bytes."""
    return json.dumps(report_dict).encode("utf-8")


@pytest.mark.unit
class TestJSONReportParsing:
    """Test parsing of RFC 8460 JSON TLS-RPT reports"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return TLSRPTService(mock_db)

    def test_parse_valid_report(self, service):
        """Test parsing a well-formed RFC 8460 report"""
        report = _make_rfc8460_report()
        data = _report_bytes(report)

        summary = service.parse_report(data)

        assert isinstance(summary, TLSRPTSummary)
        assert summary.report_id == "rpt-2024-001"
        assert summary.organization_name == "Example Corp"
        assert summary.contact_info == "mailto:tls-reports@example.com"
        assert summary.total_successful_sessions == 1000
        assert summary.total_failed_sessions == 5

    def test_parse_extracts_policy(self, service):
        """Test that policy information is correctly extracted"""
        report = _make_rfc8460_report(
            policy_type="sts",
            policy_domain="secure.example.com",
            mx_host="mx.secure.example.com",
        )
        data = _report_bytes(report)

        summary = service.parse_report(data)

        assert len(summary.policies) == 1
        policy = summary.policies[0]
        assert policy.policy_type == PolicyType.STS
        assert policy.policy_domain == "secure.example.com"
        assert policy.mx_host == "mx.secure.example.com"

    def test_parse_extracts_failure_details(self, service):
        """Test that failure details are correctly extracted"""
        report = _make_rfc8460_report()
        data = _report_bytes(report)

        summary = service.parse_report(data)

        assert len(summary.failure_details) == 1
        detail = summary.failure_details[0]
        assert detail.result_type == "certificate-expired"
        assert detail.sending_mta_ip == "203.0.113.1"
        assert detail.receiving_mx_hostname == "mx.example.com"
        assert detail.receiving_ip == "198.51.100.1"
        assert detail.failed_session_count == 5
        assert detail.failure_reason_code == "X509_V_ERR_CERT_HAS_EXPIRED"

    def test_parse_date_range(self, service):
        """Test date range parsing from ISO 8601 timestamps"""
        report = _make_rfc8460_report(
            start_datetime="2024-06-01T00:00:00Z",
            end_datetime="2024-06-02T00:00:00Z",
        )
        data = _report_bytes(report)

        summary = service.parse_report(data)

        assert summary.date_range_begin == datetime(2024, 6, 1, 0, 0, 0)
        assert summary.date_range_end == datetime(2024, 6, 2, 0, 0, 0)

    def test_parse_report_no_failures(self, service):
        """Test parsing a report with no failure details"""
        report = _make_rfc8460_report(total_failure=0, failure_details=[])
        data = _report_bytes(report)

        summary = service.parse_report(data)

        assert summary.total_failed_sessions == 0
        assert summary.failure_details == []

    def test_parse_invalid_json_raises_valueerror(self, service):
        """Test that non-JSON data raises ValueError"""
        with pytest.raises(ValueError, match="Failed to parse TLS-RPT JSON"):
            service.parse_report(b"this is not json")

    def test_parse_report_missing_fields_uses_defaults(self, service):
        """Test that missing optional fields fall back to defaults"""
        minimal = {"policies": []}
        data = _report_bytes(minimal)

        summary = service.parse_report(data)

        assert summary.organization_name == "Unknown"
        assert summary.contact_info is None
        assert summary.total_successful_sessions == 0
        assert summary.total_failed_sessions == 0


@pytest.mark.unit
class TestGzipDecompression:
    """Test gzip/zlib decompression of TLS-RPT data"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return TLSRPTService(mock_db)

    def test_parse_gzipped_report(self, service):
        """Test that gzip-compressed JSON is decompressed and parsed"""
        report = _make_rfc8460_report(org_name="Gzipped Org")
        raw_json = _report_bytes(report)
        gzipped = gzip.compress(raw_json)

        summary = service.parse_report(gzipped)

        assert summary.organization_name == "Gzipped Org"
        assert summary.total_successful_sessions == 1000

    def test_gzip_magic_bytes_detected(self, service):
        """Test that gzip magic bytes 0x1f 0x8b trigger decompression"""
        report = _make_rfc8460_report(report_id="gz-test-001")
        raw_json = _report_bytes(report)
        gzipped = gzip.compress(raw_json)

        # Verify magic bytes are present
        assert gzipped[:2] == b'\x1f\x8b'

        summary = service.parse_report(gzipped)
        assert summary.report_id == "gz-test-001"

    def test_raw_json_not_decompressed(self, service):
        """Test that raw JSON (no gzip header) is parsed directly"""
        report = _make_rfc8460_report(org_name="Raw JSON Org")
        data = _report_bytes(report)

        # Should not start with gzip magic bytes
        assert data[:2] != b'\x1f\x8b'

        summary = service.parse_report(data)
        assert summary.organization_name == "Raw JSON Org"


@pytest.mark.unit
class TestReportDeduplication:
    """Test SHA256-based report deduplication"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return TLSRPTService(mock_db)

    def test_duplicate_report_returns_existing(self, service, mock_db):
        """Test that storing a duplicate report returns the existing record"""
        report = _make_rfc8460_report()
        data = _report_bytes(report)
        report_hash = hashlib.sha256(data).hexdigest()

        existing_record = Mock(spec=TLSReport)
        existing_record.report_id = "rpt-2024-001"
        existing_record.report_hash = report_hash

        mock_db.query.return_value.filter.return_value.first.return_value = existing_record

        result = service.store_report(data, filename="report.json")

        assert result is existing_record
        # db.add should NOT be called for a duplicate
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    def test_new_report_is_stored(self, service, mock_db):
        """Test that a new report is stored in the database"""
        report = _make_rfc8460_report()
        data = _report_bytes(report)

        # No existing record with this hash
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service.store_report(data, filename="new_report.json", source_ip="10.0.0.1")

        assert mock_db.add.called
        assert mock_db.commit.called

    def test_sha256_hash_computed_on_raw_bytes(self, service, mock_db):
        """Test that the SHA256 hash is computed on the raw input bytes"""
        report = _make_rfc8460_report()
        data = _report_bytes(report)
        expected_hash = hashlib.sha256(data).hexdigest()

        mock_db.query.return_value.filter.return_value.first.return_value = None

        service.store_report(data)

        # First db.add call is the TLSReport; subsequent calls are for failure summaries
        stored = mock_db.add.call_args_list[0][0][0]
        assert stored.report_hash == expected_hash

    def test_different_data_produces_different_hash(self, service):
        """Test that different report data produces different SHA256 hashes"""
        data1 = _report_bytes(_make_rfc8460_report(org_name="Org A"))
        data2 = _report_bytes(_make_rfc8460_report(org_name="Org B"))

        hash1 = hashlib.sha256(data1).hexdigest()
        hash2 = hashlib.sha256(data2).hexdigest()

        assert hash1 != hash2


@pytest.mark.unit
class TestFailureAggregation:
    """Test failure summary aggregation logic"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return TLSRPTService(mock_db)

    def test_new_failure_summary_created(self, service, mock_db):
        """Test that a new TLSFailureSummary is created for unseen failures"""
        summary = TLSRPTSummary(
            report_id="rpt-001",
            organization_name="Test Org",
            date_range_begin=datetime(2024, 1, 15),
            date_range_end=datetime(2024, 1, 16),
            contact_info=None,
            policies=[TLSPolicy(
                policy_type=PolicyType.STS,
                policy_string=["mode: enforce"],
                policy_domain="example.com",
            )],
            failure_details=[FailureDetail(
                result_type="certificate-expired",
                sending_mta_ip="203.0.113.1",
                receiving_mx_hostname="mx.example.com",
                failed_session_count=3,
            )],
            total_successful_sessions=100,
            total_failed_sessions=3,
        )

        # No existing summary
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service._update_failure_summaries(summary)

        assert mock_db.add.called
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, TLSFailureSummary)
        assert added.policy_domain == "example.com"
        assert added.result_type == "certificate-expired"
        assert added.failure_count == 3
        assert added.report_count == 1

    def test_existing_failure_summary_updated(self, service, mock_db):
        """Test that an existing TLSFailureSummary is incremented"""
        existing = Mock(spec=TLSFailureSummary)
        existing.failure_count = 10
        existing.report_count = 2
        existing.last_seen = datetime(2024, 1, 14)

        mock_db.query.return_value.filter.return_value.first.return_value = existing

        summary = TLSRPTSummary(
            report_id="rpt-002",
            organization_name="Test Org",
            date_range_begin=datetime(2024, 1, 15),
            date_range_end=datetime(2024, 1, 16),
            contact_info=None,
            policies=[TLSPolicy(
                policy_type=PolicyType.STS,
                policy_string=[],
                policy_domain="example.com",
            )],
            failure_details=[FailureDetail(
                result_type="certificate-expired",
                sending_mta_ip="203.0.113.1",
                receiving_mx_hostname="mx.example.com",
                failed_session_count=7,
            )],
            total_successful_sessions=200,
            total_failed_sessions=7,
        )

        service._update_failure_summaries(summary)

        assert existing.failure_count == 17  # 10 + 7
        assert existing.report_count == 3    # 2 + 1


@pytest.mark.unit
class TestTrendCalculation:
    """Test failure trend query construction"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return TLSRPTService(mock_db)

    def test_get_failure_trends_returns_formatted_results(self, service, mock_db):
        """Test that get_failure_trends returns daily aggregated data"""
        mock_row = Mock()
        mock_row.date = "2024-01-15"
        mock_row.success = 500
        mock_row.failed = 10
        mock_row.reports = 3

        mock_db.query.return_value.filter.return_value.group_by.return_value \
            .order_by.return_value.all.return_value = [mock_row]

        trends = service.get_failure_trends(days=7)

        assert len(trends) == 1
        assert trends[0]["date"] == "2024-01-15"
        assert trends[0]["successful_sessions"] == 500
        assert trends[0]["failed_sessions"] == 10
        assert trends[0]["report_count"] == 3

    def test_get_failure_trends_with_domain_filter(self, service, mock_db):
        """Test that domain filter is applied to trend query"""
        mock_db.query.return_value.filter.return_value.filter.return_value \
            .group_by.return_value.order_by.return_value.all.return_value = []

        trends = service.get_failure_trends(domain="filtered.example.com", days=14)

        assert trends == []

    def test_get_failure_trends_null_values_default_to_zero(self, service, mock_db):
        """Test that null success/failed values default to 0"""
        mock_row = Mock()
        mock_row.date = "2024-01-20"
        mock_row.success = None
        mock_row.failed = None
        mock_row.reports = 1

        mock_db.query.return_value.filter.return_value.group_by.return_value \
            .order_by.return_value.all.return_value = [mock_row]

        trends = service.get_failure_trends()

        assert trends[0]["successful_sessions"] == 0
        assert trends[0]["failed_sessions"] == 0

    def test_get_domain_stats_success_rate(self, service, mock_db):
        """Test domain stats success rate calculation"""
        report1 = Mock(spec=TLSReport)
        report1.successful_session_count = 900
        report1.failed_session_count = 100
        report1.organization_name = "Reporter A"
        report1.failure_details = [
            {"result_type": "certificate-expired", "failed_session_count": 80},
            {"result_type": "starttls-not-supported", "failed_session_count": 20},
        ]

        mock_db.query.return_value.filter.return_value.all.return_value = [report1]

        stats = service.get_domain_stats("example.com", days=30)

        assert stats["domain"] == "example.com"
        assert stats["total_sessions"] == 1000
        assert stats["successful_sessions"] == 900
        assert stats["failed_sessions"] == 100
        assert stats["success_rate"] == 90.0
        assert stats["failures_by_type"]["certificate-expired"] == 80
        assert stats["failures_by_type"]["starttls-not-supported"] == 20
        assert stats["unique_reporters"] == 1

    def test_get_domain_stats_no_sessions_defaults_100_percent(self, service, mock_db):
        """Test that success rate is 100% when there are no sessions"""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        stats = service.get_domain_stats("empty.example.com")

        assert stats["success_rate"] == 100
        assert stats["total_sessions"] == 0


@pytest.mark.unit
class TestDNSRecordChecking:
    """Test TLS-RPT DNS record checking (_smtp._tls.domain)"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return TLSRPTService(mock_db)

    @patch("dns.resolver.Resolver")
    def test_check_valid_tlsrpt_record(self, mock_resolver_cls, service):
        """Test checking a valid TLS-RPT DNS record"""
        mock_resolver = mock_resolver_cls.return_value
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=TLSRPTv1; rua=mailto:tls@example.com"'
        mock_resolver.resolve.return_value = [mock_rdata]

        result = service.check_tlsrpt_record("example.com")

        mock_resolver.resolve.assert_called_with("_smtp._tls.example.com", "TXT")
        assert result["has_record"] is True
        assert result["record"] == "v=TLSRPTv1; rua=mailto:tls@example.com"
        assert "mailto:tls@example.com" in result["rua"]

    @patch("dns.resolver.Resolver")
    def test_check_record_multiple_rua(self, mock_resolver_cls, service):
        """Test parsing multiple rua URIs from a single record"""
        mock_resolver = mock_resolver_cls.return_value
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = (
            '"v=TLSRPTv1; rua=mailto:tls@example.com,https://report.example.com/api"'
        )
        mock_resolver.resolve.return_value = [mock_rdata]

        result = service.check_tlsrpt_record("example.com")

        assert len(result["rua"]) == 2
        assert "mailto:tls@example.com" in result["rua"]
        assert "https://report.example.com/api" in result["rua"]

    @patch("dns.resolver.Resolver")
    def test_check_record_not_found(self, mock_resolver_cls, service):
        """Test handling when no TLS-RPT record exists"""
        mock_resolver = mock_resolver_cls.return_value
        mock_resolver.resolve.side_effect = Exception("NXDOMAIN")

        result = service.check_tlsrpt_record("no-record.example.com")

        assert result["has_record"] is False
        assert result["record"] is None
        assert result["rua"] == []
        assert len(result["issues"]) == 1

    def test_generate_tlsrpt_record(self, service):
        """Test generating a TLS-RPT DNS TXT record"""
        result = service.generate_tlsrpt_record(
            domain="example.com",
            rua=["mailto:tls@example.com"],
        )

        assert result["record_name"] == "_smtp._tls.example.com"
        assert result["record_type"] == "TXT"
        assert result["record_value"] == "v=TLSRPTv1; rua=mailto:tls@example.com"
        assert result["ttl"] == 3600

    def test_generate_tlsrpt_record_multiple_rua(self, service):
        """Test generating a record with multiple rua destinations"""
        result = service.generate_tlsrpt_record(
            domain="example.com",
            rua=["mailto:tls@example.com", "https://collector.example.com/v1"],
        )

        assert "mailto:tls@example.com,https://collector.example.com/v1" in result["record_value"]
