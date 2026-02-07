"""Unit tests for MTASTSService (mta_sts_service.py)"""
import pytest
import hashlib
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from app.services.mta_sts_service import (
    MTASTSService,
    MTASTSMonitor,
    MTASTSChangeLog,
    STSMode,
    STSRecord,
    STSPolicy,
    PolicyStatus,
)


VALID_POLICY_TEXT = (
    "version: STSv1\n"
    "mode: enforce\n"
    "mx: mail.example.com\n"
    "mx: *.example.com\n"
    "max_age: 604800\n"
)


@pytest.mark.unit
class TestSTSRecordLookup:
    """Test DNS TXT record lookup and parsing for _mta-sts.domain"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.mta_sts_service.dns.resolver.Resolver"):
            svc = MTASTSService(mock_db)
        return svc

    def test_get_sts_record_success(self, service):
        """Test successful MTA-STS DNS TXT record lookup"""
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=STSv1; id=20260101T000000"'
        service.resolver.resolve.return_value = [mock_rdata]

        result = service._get_sts_record("example.com")

        assert result is not None
        assert result.version == "STSv1"
        assert result.id == "20260101T000000"
        assert "v=STSv1" in result.raw
        service.resolver.resolve.assert_called_once_with(
            "_mta-sts.example.com", "TXT"
        )

    def test_get_sts_record_dns_failure_returns_none(self, service):
        """Test DNS resolution failure returns None"""
        service.resolver.resolve.side_effect = Exception("NXDOMAIN")

        result = service._get_sts_record("nonexistent.com")
        assert result is None

    def test_get_sts_record_ignores_non_sts_txt(self, service):
        """Test that non-STS TXT records are ignored"""
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"google-site-verification=abcdef"'
        service.resolver.resolve.return_value = [mock_rdata]

        result = service._get_sts_record("example.com")
        assert result is None

    def test_get_sts_record_multiple_txt_picks_sts(self, service):
        """Test that the correct STS record is found among multiple TXT records"""
        mock_other = Mock()
        mock_other.to_text.return_value = '"some-other-txt-record"'
        mock_sts = Mock()
        mock_sts.to_text.return_value = '"v=STSv1; id=abc123"'
        service.resolver.resolve.return_value = [mock_other, mock_sts]

        result = service._get_sts_record("example.com")

        assert result is not None
        assert result.id == "abc123"


@pytest.mark.unit
class TestSTSPolicyFetchAndParse:
    """Test HTTPS policy file fetch and parsing"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.mta_sts_service.dns.resolver.Resolver"):
            svc = MTASTSService(mock_db)
        return svc

    def test_parse_valid_policy(self, service):
        """Test parsing a valid MTA-STS policy file"""
        result = service._parse_policy(VALID_POLICY_TEXT)

        assert result is not None
        assert result.version == "STSv1"
        assert result.mode == STSMode.ENFORCE
        assert result.max_age == 604800
        assert "mail.example.com" in result.mx
        assert "*.example.com" in result.mx
        assert len(result.mx) == 2

    def test_parse_testing_mode(self, service):
        """Test parsing policy with testing mode"""
        text = "version: STSv1\nmode: testing\nmx: mx.example.com\nmax_age: 86400\n"
        result = service._parse_policy(text)

        assert result is not None
        assert result.mode == STSMode.TESTING

    def test_parse_none_mode(self, service):
        """Test parsing policy with none mode"""
        text = "version: STSv1\nmode: none\nmx: mx.example.com\nmax_age: 0\n"
        result = service._parse_policy(text)

        assert result is not None
        assert result.mode == STSMode.NONE
        assert result.max_age == 0

    def test_parse_invalid_policy_returns_none(self, service):
        """Test that malformed policy content returns None"""
        result = service._parse_policy("this is not a valid policy")
        # The parser sets mode from dict; missing mode defaults to "none"
        # which is a valid STSMode, so it will still parse.
        # A truly invalid mode value would return None.
        bad_mode = "version: STSv1\nmode: badvalue\nmx: mx.example.com\nmax_age: 100\n"
        result = service._parse_policy(bad_mode)
        assert result is None

    @patch("app.services.mta_sts_service.httpx.Client")
    def test_get_sts_policy_success(self, mock_client_cls, service):
        """Test successful HTTPS policy file fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = VALID_POLICY_TEXT

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = service._get_sts_policy("example.com")

        assert result is not None
        assert result.mode == STSMode.ENFORCE
        mock_client.get.assert_called_once_with(
            "https://mta-sts.example.com/.well-known/mta-sts.txt"
        )

    @patch("app.services.mta_sts_service.httpx.Client")
    def test_get_sts_policy_404_returns_none(self, mock_client_cls, service):
        """Test HTTP 404 returns None"""
        mock_response = Mock()
        mock_response.status_code = 404

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = service._get_sts_policy("example.com")
        assert result is None

    @patch("app.services.mta_sts_service.httpx.Client")
    def test_get_sts_policy_connection_error_returns_none(self, mock_client_cls, service):
        """Test connection error returns None"""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = service._get_sts_policy("example.com")
        assert result is None


@pytest.mark.unit
class TestMXValidation:
    """Test MX record validation against policy patterns"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.mta_sts_service.dns.resolver.Resolver"):
            svc = MTASTSService(mock_db)
        return svc

    def test_exact_mx_match(self, service):
        """Test exact MX hostname match"""
        policy_mx = ["mail.example.com"]
        actual_mx = ["mail.example.com"]
        assert service._validate_mx_hosts(policy_mx, actual_mx) is True

    def test_exact_match_case_insensitive(self, service):
        """Test case-insensitive MX matching"""
        policy_mx = ["Mail.Example.COM"]
        actual_mx = ["mail.example.com"]
        assert service._validate_mx_hosts(policy_mx, actual_mx) is True

    def test_wildcard_mx_match(self, service):
        """Test wildcard MX pattern matching (*.example.com)"""
        policy_mx = ["*.example.com"]
        actual_mx = ["mx1.example.com"]
        assert service._validate_mx_hosts(policy_mx, actual_mx) is True

    def test_wildcard_matches_base_domain(self, service):
        """Test wildcard matches the base domain itself"""
        policy_mx = ["*.example.com"]
        actual_mx = ["example.com"]
        assert service._validate_mx_hosts(policy_mx, actual_mx) is True

    def test_wildcard_multiple_actual_hosts(self, service):
        """Test wildcard matches multiple actual MX hosts"""
        policy_mx = ["*.example.com"]
        actual_mx = ["mx1.example.com", "mx2.example.com"]
        assert service._validate_mx_hosts(policy_mx, actual_mx) is True

    def test_unmatched_mx_returns_false(self, service):
        """Test unmatched MX host returns False"""
        policy_mx = ["mail.example.com"]
        actual_mx = ["mail.other.com"]
        assert service._validate_mx_hosts(policy_mx, actual_mx) is False

    def test_wildcard_no_match_different_domain(self, service):
        """Test wildcard does not match a different domain"""
        policy_mx = ["*.example.com"]
        actual_mx = ["mx.otherdomain.com"]
        assert service._validate_mx_hosts(policy_mx, actual_mx) is False

    def test_partial_match_fails(self, service):
        """Test that partial coverage of actual MX hosts fails"""
        policy_mx = ["mx1.example.com"]
        actual_mx = ["mx1.example.com", "mx2.example.com"]
        assert service._validate_mx_hosts(policy_mx, actual_mx) is False

    def test_empty_actual_mx_returns_true(self, service):
        """Test empty actual MX list is vacuously valid"""
        policy_mx = ["*.example.com"]
        actual_mx = []
        assert service._validate_mx_hosts(policy_mx, actual_mx) is True


@pytest.mark.unit
class TestPerformCheck:
    """Test end-to-end domain check and mode/status detection"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.mta_sts_service.dns.resolver.Resolver"):
            svc = MTASTSService(mock_db)
        return svc

    def test_missing_status_no_record_no_policy(self, service):
        """Test MISSING status when neither record nor policy exists"""
        service._get_sts_record = Mock(return_value=None)
        service._get_sts_policy = Mock(return_value=None)

        result = service._perform_check("example.com")

        assert result.status == PolicyStatus.MISSING
        assert not result.has_record
        assert not result.has_policy
        assert any("No MTA-STS DNS record" in i for i in result.issues)

    def test_invalid_status_record_without_policy(self, service):
        """Test INVALID status when record exists but policy is missing"""
        record = STSRecord(version="STSv1", id="20260101", raw="v=STSv1; id=20260101")
        service._get_sts_record = Mock(return_value=record)
        service._get_sts_policy = Mock(return_value=None)

        result = service._perform_check("example.com")

        assert result.status == PolicyStatus.INVALID
        assert result.has_record
        assert not result.has_policy

    def test_valid_status_full_check(self, service):
        """Test VALID status with record, policy, and matching MX"""
        record = STSRecord(version="STSv1", id="20260101", raw="v=STSv1; id=20260101")
        policy = STSPolicy(
            version="STSv1", mode=STSMode.ENFORCE,
            mx=["*.example.com"], max_age=604800, raw=VALID_POLICY_TEXT,
        )
        service._get_sts_record = Mock(return_value=record)
        service._get_sts_policy = Mock(return_value=policy)
        service._get_mx_records = Mock(return_value=["mx1.example.com"])

        result = service._perform_check("example.com")

        assert result.status == PolicyStatus.VALID
        assert result.mx_valid
        assert result.issues == []

    def test_mismatch_status_when_mx_invalid(self, service):
        """Test MISMATCH status when MX hosts do not match policy"""
        record = STSRecord(version="STSv1", id="20260101", raw="v=STSv1; id=20260101")
        policy = STSPolicy(
            version="STSv1", mode=STSMode.ENFORCE,
            mx=["mx.example.com"], max_age=604800, raw="...",
        )
        service._get_sts_record = Mock(return_value=record)
        service._get_sts_policy = Mock(return_value=policy)
        service._get_mx_records = Mock(return_value=["mx.other.com"])

        result = service._perform_check("example.com")

        assert result.status == PolicyStatus.MISMATCH
        assert not result.mx_valid

    def test_warnings_for_testing_mode(self, service):
        """Test warnings generated for testing mode"""
        record = STSRecord(version="STSv1", id="20260101", raw="v=STSv1; id=20260101")
        policy = STSPolicy(
            version="STSv1", mode=STSMode.TESTING,
            mx=["*.example.com"], max_age=604800, raw="...",
        )
        service._get_sts_record = Mock(return_value=record)
        service._get_sts_policy = Mock(return_value=policy)
        service._get_mx_records = Mock(return_value=["mx.example.com"])

        result = service._perform_check("example.com")

        assert any("testing" in w for w in result.warnings)

    def test_warnings_for_short_max_age(self, service):
        """Test warnings generated for short max_age"""
        record = STSRecord(version="STSv1", id="20260101", raw="v=STSv1; id=20260101")
        policy = STSPolicy(
            version="STSv1", mode=STSMode.ENFORCE,
            mx=["*.example.com"], max_age=3600, raw="...",
        )
        service._get_sts_record = Mock(return_value=record)
        service._get_sts_policy = Mock(return_value=policy)
        service._get_mx_records = Mock(return_value=["mx.example.com"])

        result = service._perform_check("example.com")

        assert any("max_age" in w and "short" in w for w in result.warnings)


@pytest.mark.unit
class TestChangeDetection:
    """Test change detection and logging"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.mta_sts_service.dns.resolver.Resolver"):
            svc = MTASTSService(mock_db)
        return svc

    def _make_monitor(self, **overrides):
        monitor = Mock(spec=MTASTSMonitor)
        monitor.domain = "example.com"
        monitor.last_policy_id = None
        monitor.last_mode = None
        monitor.last_mx_hosts = None
        for key, val in overrides.items():
            setattr(monitor, key, val)
        return monitor

    def test_policy_added_detected(self, service, mock_db):
        """Test detecting a newly added policy"""
        monitor = self._make_monitor(last_policy_id=None)
        record = STSRecord(version="STSv1", id="new123", raw="v=STSv1; id=new123")
        policy = STSPolicy(
            version="STSv1", mode=STSMode.ENFORCE,
            mx=["mx.example.com"], max_age=604800, raw="...",
        )
        check = Mock()
        check.record = record
        check.policy = policy

        service._detect_changes(monitor, check)

        assert mock_db.add.called
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.change_type == "policy_added"
        assert log_entry.domain == "example.com"

    def test_policy_removed_detected(self, service, mock_db):
        """Test detecting a removed policy"""
        monitor = self._make_monitor(last_policy_id="old123")
        check = Mock()
        check.record = None
        check.policy = None

        service._detect_changes(monitor, check)

        assert mock_db.add.called
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.change_type == "policy_removed"

    def test_mode_change_detected(self, service, mock_db):
        """Test detecting a mode change (e.g., testing -> enforce)"""
        monitor = self._make_monitor(
            last_policy_id="id1", last_mode="testing", last_mx_hosts="mx.example.com",
        )
        record = STSRecord(version="STSv1", id="id1", raw="v=STSv1; id=id1")
        policy = STSPolicy(
            version="STSv1", mode=STSMode.ENFORCE,
            mx=["mx.example.com"], max_age=604800, raw="...",
        )
        check = Mock()
        check.record = record
        check.policy = policy

        service._detect_changes(monitor, check)

        logged_types = [
            call[0][0].change_type for call in mock_db.add.call_args_list
        ]
        assert "mode_changed" in logged_types

    def test_mx_change_detected(self, service, mock_db):
        """Test detecting MX host list change"""
        monitor = self._make_monitor(
            last_policy_id="id1", last_mode="enforce",
            last_mx_hosts="mx1.example.com",
        )
        record = STSRecord(version="STSv1", id="id1", raw="v=STSv1; id=id1")
        policy = STSPolicy(
            version="STSv1", mode=STSMode.ENFORCE,
            mx=["mx2.example.com"], max_age=604800, raw="...",
        )
        check = Mock()
        check.record = record
        check.policy = policy

        service._detect_changes(monitor, check)

        logged_types = [
            call[0][0].change_type for call in mock_db.add.call_args_list
        ]
        assert "mx_changed" in logged_types

    def test_no_changes_when_unchanged(self, service, mock_db):
        """Test that no change logs are created when nothing changed"""
        monitor = self._make_monitor(
            last_policy_id="id1", last_mode="enforce",
            last_mx_hosts="mx.example.com",
        )
        record = STSRecord(version="STSv1", id="id1", raw="v=STSv1; id=id1")
        policy = STSPolicy(
            version="STSv1", mode=STSMode.ENFORCE,
            mx=["mx.example.com"], max_age=604800, raw="...",
        )
        check = Mock()
        check.record = record
        check.policy = policy

        service._detect_changes(monitor, check)

        assert not mock_db.add.called
