"""Unit tests for ThreatIntelService (threat_intel.py)"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.services.threat_intel import ThreatIntelService, ThreatLevel, ThreatInfo


@pytest.mark.unit
class TestAbuseIPDBResponses:
    """Test mock AbuseIPDB API responses"""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    @pytest.fixture
    def mock_settings(self):
        settings = Mock()
        settings.abuseipdb_api_key = "test-api-key-123"
        return settings

    @pytest.fixture
    def service(self, mock_db, mock_settings):
        with patch("app.services.threat_intel.get_settings", return_value=mock_settings):
            return ThreatIntelService(mock_db)

    def test_check_ip_abuseipdb_success(self, service, mock_db):
        """Test successful AbuseIPDB lookup"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "ipAddress": "1.2.3.4",
                "abuseConfidenceScore": 85,
                "totalReports": 42,
                "lastReportedAt": "2024-01-15T12:00:00Z",
                "isWhitelisted": False,
                "isTor": False,
                "isPublic": True,
                "isp": "Example ISP",
                "domain": "example.com",
                "countryCode": "US",
                "usageType": "Data Center/Web Hosting/Transit",
                "reports": [
                    {"categories": [14, 18]},
                    {"categories": [22]},
                ]
            }
        }
        mock_response.raise_for_status = Mock()

        with patch("app.services.threat_intel.requests.get", return_value=mock_response):
            result = service.check_ip_abuseipdb("1.2.3.4", use_cache=False)

        assert result is not None
        assert result.ip_address == "1.2.3.4"
        assert result.abuse_score == 85
        assert result.threat_level == ThreatLevel.CRITICAL  # 80+
        assert result.total_reports == 42
        assert result.isp == "Example ISP"
        assert result.country_code == "US"
        assert "Port Scan" in result.categories
        assert "Brute-Force" in result.categories
        assert "SSH" in result.categories

    def test_check_ip_clean(self, service, mock_db):
        """Test lookup for a clean IP"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "ipAddress": "8.8.8.8",
                "abuseConfidenceScore": 0,
                "totalReports": 0,
                "lastReportedAt": None,
                "isWhitelisted": True,
                "isTor": False,
                "isPublic": True,
                "isp": "Google LLC",
                "domain": "google.com",
                "countryCode": "US",
                "usageType": "Content Delivery Network",
                "reports": []
            }
        }
        mock_response.raise_for_status = Mock()

        with patch("app.services.threat_intel.requests.get", return_value=mock_response):
            result = service.check_ip_abuseipdb("8.8.8.8", use_cache=False)

        assert result.threat_level == ThreatLevel.CLEAN
        assert result.abuse_score == 0
        assert result.categories == []


@pytest.mark.unit
class TestThreatIntelCache:
    """Test cache behavior (hit/miss)"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_settings(self):
        settings = Mock()
        settings.abuseipdb_api_key = "test-api-key"
        return settings

    @pytest.fixture
    def service(self, mock_db, mock_settings):
        with patch("app.services.threat_intel.get_settings", return_value=mock_settings):
            return ThreatIntelService(mock_db)

    def test_cache_hit_returns_cached_data(self, service, mock_db):
        """Test that a cache hit returns data without API call"""
        cached = Mock()
        cached.ip_address = "1.2.3.4"
        cached.threat_level = "high"
        cached.abuse_score = 65
        cached.total_reports = 10
        cached.last_reported = datetime(2024, 1, 10)
        cached.is_whitelisted = 0
        cached.is_tor = 0
        cached.isp = "Cached ISP"
        cached.domain = "cached.com"
        cached.country_code = "GB"
        cached.usage_type = "ISP"
        cached.categories = ["Port Scan"]
        cached.created_at = datetime(2024, 1, 15)

        mock_db.query.return_value.filter.return_value.first.return_value = cached

        result = service.check_ip_abuseipdb("1.2.3.4", use_cache=True)

        assert result is not None
        assert result.abuse_score == 65
        assert result.source == "abuseipdb_cache"

    def test_cache_miss_triggers_api_call(self, service, mock_db):
        """Test that a cache miss triggers an API call"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "ipAddress": "5.6.7.8",
                "abuseConfidenceScore": 30,
                "totalReports": 5,
                "lastReportedAt": None,
                "isWhitelisted": False,
                "isTor": False,
                "isPublic": True,
                "reports": []
            }
        }
        mock_response.raise_for_status = Mock()

        with patch("app.services.threat_intel.requests.get", return_value=mock_response) as mock_get:
            result = service.check_ip_abuseipdb("5.6.7.8", use_cache=True)

        assert mock_get.called
        assert result.abuse_score == 30

    def test_cache_bypass_always_calls_api(self, service, mock_db):
        """Test that use_cache=False always calls the API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "ipAddress": "1.1.1.1",
                "abuseConfidenceScore": 10,
                "totalReports": 2,
                "lastReportedAt": None,
                "isWhitelisted": False,
                "isTor": False,
                "isPublic": True,
                "reports": []
            }
        }
        mock_response.raise_for_status = Mock()

        with patch("app.services.threat_intel.requests.get", return_value=mock_response) as mock_get:
            result = service.check_ip_abuseipdb("1.1.1.1", use_cache=False)

        assert mock_get.called


@pytest.mark.unit
class TestThreatIntelErrorHandling:
    """Test error handling for API failures"""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    @pytest.fixture
    def mock_settings(self):
        settings = Mock()
        settings.abuseipdb_api_key = "test-api-key"
        return settings

    @pytest.fixture
    def service(self, mock_db, mock_settings):
        with patch("app.services.threat_intel.get_settings", return_value=mock_settings):
            return ThreatIntelService(mock_db)

    def test_api_timeout_returns_none(self, service):
        """Test that API timeout returns None gracefully"""
        import requests.exceptions

        with patch("app.services.threat_intel.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
            result = service.check_ip_abuseipdb("1.2.3.4", use_cache=False)

        assert result is None

    def test_api_connection_error_returns_none(self, service):
        """Test that connection error returns None gracefully"""
        import requests.exceptions

        with patch("app.services.threat_intel.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Failed to connect")
            result = service.check_ip_abuseipdb("1.2.3.4", use_cache=False)

        assert result is None

    def test_api_http_error_returns_none(self, service):
        """Test that HTTP error (e.g. 429 rate limit) returns None"""
        import requests.exceptions

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")

        with patch("app.services.threat_intel.requests.get", return_value=mock_response):
            result = service.check_ip_abuseipdb("1.2.3.4", use_cache=False)

        assert result is None

    def test_no_api_key_returns_none(self, mock_db):
        """Test that missing API key returns None"""
        settings = Mock()
        settings.abuseipdb_api_key = None

        with patch("app.services.threat_intel.get_settings", return_value=settings):
            service = ThreatIntelService(mock_db)

        result = service.check_ip_abuseipdb("1.2.3.4", use_cache=False)
        assert result is None

    def test_check_ip_fallback_to_unknown(self, mock_db):
        """Test check_ip returns UNKNOWN when no sources available"""
        settings = Mock()
        settings.abuseipdb_api_key = None

        with patch("app.services.threat_intel.get_settings", return_value=settings):
            service = ThreatIntelService(mock_db)

        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = service.check_ip("1.2.3.4", use_cache=False)

        assert result is not None
        assert result.threat_level == ThreatLevel.UNKNOWN
        assert result.source == "none"


@pytest.mark.unit
class TestThreatLevelClassification:
    """Test score to threat level mapping"""

    @pytest.fixture
    def service(self):
        mock_db = MagicMock()
        mock_settings = Mock()
        mock_settings.abuseipdb_api_key = None
        with patch("app.services.threat_intel.get_settings", return_value=mock_settings):
            return ThreatIntelService(mock_db)

    def test_critical_threshold(self, service):
        assert service._score_to_threat_level(80) == ThreatLevel.CRITICAL
        assert service._score_to_threat_level(100) == ThreatLevel.CRITICAL

    def test_high_threshold(self, service):
        assert service._score_to_threat_level(50) == ThreatLevel.HIGH
        assert service._score_to_threat_level(79) == ThreatLevel.HIGH

    def test_medium_threshold(self, service):
        assert service._score_to_threat_level(25) == ThreatLevel.MEDIUM
        assert service._score_to_threat_level(49) == ThreatLevel.MEDIUM

    def test_low_threshold(self, service):
        assert service._score_to_threat_level(1) == ThreatLevel.LOW
        assert service._score_to_threat_level(24) == ThreatLevel.LOW

    def test_clean_threshold(self, service):
        assert service._score_to_threat_level(0) == ThreatLevel.CLEAN
