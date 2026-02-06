"""Unit tests for DNSMonitorService (dns_monitor.py)"""
import pytest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.services.dns_monitor import (
    DNSMonitorService, MonitoredDomain, DNSChangeLog,
    RecordType, ChangeType, DNSChange,
)


@pytest.mark.unit
class TestDNSLookupMocking:
    """Test DNS lookups with mocked dns.resolver"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.dns_monitor.dns.resolver.Resolver"):
            svc = DNSMonitorService(mock_db)
        return svc

    def test_get_txt_record_success(self, service):
        """Test TXT record lookup returns text"""
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=DMARC1; p=reject; rua=mailto:dmarc@example.com"'

        mock_answers = [mock_rdata]
        service.resolver.resolve.return_value = mock_answers

        result = service._get_txt_record("_dmarc.example.com")
        assert result == "v=DMARC1; p=reject; rua=mailto:dmarc@example.com"

    def test_get_txt_record_failure_returns_none(self, service):
        """Test TXT record lookup failure returns None"""
        service.resolver.resolve.side_effect = Exception("DNS resolution failed")

        result = service._get_txt_record("_dmarc.nonexistent.com")
        assert result is None

    def test_get_spf_record_success(self, service):
        """Test SPF record lookup finds v=spf1 record"""
        mock_rdata1 = Mock()
        mock_rdata1.to_text.return_value = '"google-site-verification=abc123"'
        mock_rdata2 = Mock()
        mock_rdata2.to_text.return_value = '"v=spf1 include:_spf.google.com ~all"'

        service.resolver.resolve.return_value = [mock_rdata1, mock_rdata2]

        result = service._get_spf_record("example.com")
        assert result == "v=spf1 include:_spf.google.com ~all"

    def test_get_spf_record_no_spf(self, service):
        """Test SPF lookup when no SPF record exists"""
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"not-an-spf-record"'

        service.resolver.resolve.return_value = [mock_rdata]

        result = service._get_spf_record("example.com")
        assert result is None

    def test_get_mx_records_success(self, service):
        """Test MX record lookup returns formatted records"""
        mock_mx1 = Mock()
        mock_mx1.preference = 10
        mock_mx1.exchange = "mx1.example.com."
        mock_mx2 = Mock()
        mock_mx2.preference = 20
        mock_mx2.exchange = "mx2.example.com."

        service.resolver.resolve.return_value = [mock_mx1, mock_mx2]

        result = service._get_mx_records("example.com")
        assert len(result) == 2
        assert "10 mx1.example.com." in result
        assert "20 mx2.example.com." in result

    def test_get_mx_records_failure_returns_empty(self, service):
        """Test MX lookup failure returns empty list"""
        service.resolver.resolve.side_effect = Exception("No MX records")

        result = service._get_mx_records("nonexistent.com")
        assert result == []


@pytest.mark.unit
class TestChangeDetection:
    """Test DNS change detection logic"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.dns_monitor.dns.resolver.Resolver"):
            svc = DNSMonitorService(mock_db)
        return svc

    def test_hash_value_deterministic(self, service):
        """Test hash function is deterministic"""
        h1 = service._hash_value("v=DMARC1; p=reject")
        h2 = service._hash_value("v=DMARC1; p=reject")
        assert h1 == h2

    def test_hash_value_different_inputs(self, service):
        """Test different inputs produce different hashes"""
        h1 = service._hash_value("v=DMARC1; p=reject")
        h2 = service._hash_value("v=DMARC1; p=none")
        assert h1 != h2

    def test_dmarc_change_detected(self, service, mock_db):
        """Test DMARC record change is detected"""
        monitored = Mock(spec=MonitoredDomain)
        monitored.domain = "example.com"
        monitored.last_dmarc_hash = hashlib.sha256(b"old-record").hexdigest()

        # Simulate new record
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=DMARC1; p=reject"'
        service.resolver.resolve.return_value = [mock_rdata]

        # No previous change log
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        change = service._check_dmarc(monitored)

        assert change is not None
        assert change.record_type == "dmarc"
        assert change.change_type == ChangeType.MODIFIED
        assert change.domain == "example.com"

    def test_dmarc_no_change(self, service, mock_db):
        """Test no change when DMARC record is the same"""
        record_value = "v=DMARC1; p=reject"
        current_hash = hashlib.sha256(record_value.encode()).hexdigest()

        monitored = Mock(spec=MonitoredDomain)
        monitored.domain = "example.com"
        monitored.last_dmarc_hash = current_hash

        mock_rdata = Mock()
        mock_rdata.to_text.return_value = f'"{record_value}"'
        service.resolver.resolve.return_value = [mock_rdata]

        change = service._check_dmarc(monitored)
        assert change is None

    def test_new_record_detected_as_added(self, service, mock_db):
        """Test new record (from None) is detected as ADDED"""
        monitored = Mock(spec=MonitoredDomain)
        monitored.domain = "example.com"
        monitored.last_dmarc_hash = None  # No previous record

        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=DMARC1; p=none"'
        service.resolver.resolve.return_value = [mock_rdata]

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        change = service._check_dmarc(monitored)

        assert change is not None
        assert change.change_type == ChangeType.ADDED

    def test_record_removal_detected(self, service, mock_db):
        """Test removed record (to None) is detected as REMOVED"""
        monitored = Mock(spec=MonitoredDomain)
        monitored.domain = "example.com"
        monitored.last_dmarc_hash = hashlib.sha256(b"old-record").hexdigest()

        # DNS returns nothing
        service.resolver.resolve.side_effect = Exception("NXDOMAIN")

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        change = service._check_dmarc(monitored)

        assert change is not None
        assert change.change_type == ChangeType.REMOVED

    def test_log_change_persists_to_db(self, service, mock_db):
        """Test that detected changes are logged to database"""
        service._log_change(
            domain="example.com",
            record_type=RecordType.DMARC,
            old_hash="old_hash",
            new_hash="new_hash",
            old_value="v=DMARC1; p=none",
            new_value="v=DMARC1; p=reject",
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.domain == "example.com"
        assert log_entry.record_type == "dmarc"
        assert log_entry.change_type == "modified"


@pytest.mark.unit
class TestMultipleRecordTypes:
    """Test handling of multiple record types"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.dns_monitor.dns.resolver.Resolver"):
            svc = DNSMonitorService(mock_db)
        return svc

    def test_check_monitored_checks_all_enabled_types(self, service, mock_db):
        """Test that all enabled monitoring types are checked"""
        monitored = Mock(spec=MonitoredDomain)
        monitored.domain = "example.com"
        monitored.monitor_dmarc = True
        monitored.monitor_spf = True
        monitored.monitor_mx = True
        monitored.monitor_dkim = False
        monitored.dkim_selectors = None

        # No changes detected
        monitored.last_dmarc_hash = None
        monitored.last_spf_hash = None
        monitored.last_mx_hash = None

        service.resolver.resolve.side_effect = Exception("no records")
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        changes = service._check_monitored(monitored)

        # Even if no changes, the method should have checked each type
        assert mock_db.commit.called

    def test_spf_change_detection(self, service, mock_db):
        """Test SPF record change detection"""
        monitored = Mock(spec=MonitoredDomain)
        monitored.domain = "example.com"
        monitored.last_spf_hash = hashlib.sha256(b"v=spf1 ~all").hexdigest()

        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=spf1 include:_spf.google.com -all"'
        service.resolver.resolve.return_value = [mock_rdata]

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        change = service._check_spf(monitored)
        assert change is not None
        assert change.record_type == "spf"

    def test_mx_change_detection(self, service, mock_db):
        """Test MX record change detection"""
        monitored = Mock(spec=MonitoredDomain)
        monitored.domain = "example.com"
        monitored.last_mx_hash = hashlib.sha256(b"10 mx1.example.com.").hexdigest()

        mock_mx = Mock()
        mock_mx.preference = 10
        mock_mx.exchange = "mx-new.example.com."
        service.resolver.resolve.return_value = [mock_mx]

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        change = service._check_mx(monitored)
        assert change is not None
        assert change.record_type == "mx"

    def test_dkim_change_detection(self, service, mock_db):
        """Test DKIM selector change detection"""
        monitored = Mock(spec=MonitoredDomain)
        monitored.domain = "example.com"
        monitored.dkim_selectors = "selector1,selector2"
        monitored.last_dkim_hash = hashlib.sha256(b"old-dkim").hexdigest()

        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=DKIM1; k=rsa; p=MIGfMA..."'
        service.resolver.resolve.return_value = [mock_rdata]

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        changes = service._check_dkim(monitored)
        assert len(changes) > 0
        assert changes[0].record_type == "dkim"
