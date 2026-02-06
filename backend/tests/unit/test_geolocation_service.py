"""Unit tests for GeoLocationService (geolocation.py)"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from app.services.geolocation import GeoLocationService


@pytest.mark.unit
class TestIPLookupWithMockReader:
    """Test IP lookup using a mocked MaxMind reader"""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    @pytest.fixture
    def mock_reader_response(self):
        """Create a mock MaxMind city response"""
        response = Mock()
        response.country.iso_code = "US"
        response.country.name = "United States"
        response.city.name = "Mountain View"
        response.location.latitude = 37.386
        response.location.longitude = -122.084
        response.location.time_zone = "America/Los_Angeles"
        response.continent.code = "NA"
        response.continent.name = "North America"
        return response

    @pytest.fixture
    def service(self, mock_db, mock_reader_response):
        with patch("app.services.geolocation.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("geoip2.database.Reader") as mock_reader_cls:
                mock_reader = Mock()
                mock_reader.city.return_value = mock_reader_response
                mock_reader_cls.return_value = mock_reader

                svc = GeoLocationService(mock_db, "/fake/path/GeoLite2-City.mmdb")
                svc.reader = mock_reader
                return svc

    def test_lookup_ip_returns_geo_data(self, service, mock_db):
        """Test successful IP lookup returns expected data structure"""
        result = service.lookup_ip("8.8.8.8", use_cache=False)

        assert result is not None
        assert result["country_code"] == "US"
        assert result["country_name"] == "United States"
        assert result["city_name"] == "Mountain View"
        assert result["latitude"] == 37.386
        assert result["longitude"] == -122.084

    def test_lookup_ip_returns_all_fields(self, service, mock_db):
        """Test that lookup returns all expected fields"""
        result = service.lookup_ip("8.8.8.8", use_cache=False)

        expected_keys = [
            "ip_address", "country_code", "country_name", "city_name",
            "latitude", "longitude", "timezone", "continent_code",
            "continent_name", "asn", "asn_organization", "isp",
        ]
        for key in expected_keys:
            assert key in result

    def test_lookup_ip_caches_result(self, service, mock_db):
        """Test that lookup saves result to cache"""
        service.lookup_ip("8.8.8.8", use_cache=True)

        # Should have committed to save cache
        assert mock_db.commit.called


@pytest.mark.unit
class TestCacheHitVsMiss:
    """Test cache hit vs miss behavior"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_cache_hit_returns_cached_data(self, mock_db):
        """Test that a cache hit returns data without reader lookup"""
        cached_entry = Mock()
        cached_entry.ip_address = "1.2.3.4"
        cached_entry.country_code = "GB"
        cached_entry.country_name = "United Kingdom"
        cached_entry.city_name = "London"
        cached_entry.latitude = 51.5
        cached_entry.longitude = -0.1
        cached_entry.timezone = "Europe/London"
        cached_entry.continent_code = "EU"
        cached_entry.continent_name = "Europe"
        cached_entry.asn = None
        cached_entry.asn_organization = None
        cached_entry.isp = None

        mock_db.query.return_value.filter.return_value.first.return_value = cached_entry

        with patch("app.services.geolocation.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("geoip2.database.Reader"):
                service = GeoLocationService(mock_db, "/fake/path.mmdb")

        result = service.lookup_ip("1.2.3.4", use_cache=True)

        assert result is not None
        assert result["country_code"] == "GB"
        # Reader should not have been called since cache hit
        service.reader.city.assert_not_called()

    def test_cache_miss_queries_reader(self, mock_db):
        """Test that a cache miss triggers reader lookup"""
        # No cache entry
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.services.geolocation.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("geoip2.database.Reader") as mock_reader_cls:
                mock_reader = Mock()
                response = Mock()
                response.country.iso_code = "DE"
                response.country.name = "Germany"
                response.city.name = "Berlin"
                response.location.latitude = 52.52
                response.location.longitude = 13.405
                response.location.time_zone = "Europe/Berlin"
                response.continent.code = "EU"
                response.continent.name = "Europe"
                mock_reader.city.return_value = response
                mock_reader_cls.return_value = mock_reader

                service = GeoLocationService(mock_db, "/fake/path.mmdb")

        result = service.lookup_ip("1.1.1.1", use_cache=True)

        assert result is not None
        assert result["country_code"] == "DE"
        service.reader.city.assert_called_once_with("1.1.1.1")

    def test_bulk_lookup_uses_cache(self, mock_db):
        """Test bulk lookup checks cache first"""
        cached = Mock()
        cached.ip_address = "1.1.1.1"
        cached.country_code = "US"
        cached.country_name = "United States"
        cached.city_name = "Test"
        cached.latitude = 0.0
        cached.longitude = 0.0
        cached.timezone = "UTC"
        cached.continent_code = "NA"
        cached.continent_name = "North America"
        cached.asn = None
        cached.asn_organization = None
        cached.isp = None

        mock_db.query.return_value.filter.return_value.first.return_value = cached

        with patch("app.services.geolocation.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("geoip2.database.Reader"):
                service = GeoLocationService(mock_db, "/fake/path.mmdb")

        results = service.lookup_ips_bulk(["1.1.1.1", "2.2.2.2"])
        assert "1.1.1.1" in results


@pytest.mark.unit
class TestGracefulDegradation:
    """Test graceful degradation when MaxMind DB missing"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_no_reader_when_db_missing(self, mock_db):
        """Test that service initializes with reader=None when DB file is missing"""
        with patch("app.services.geolocation.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            service = GeoLocationService(mock_db, "/nonexistent/GeoLite2-City.mmdb")

        assert service.reader is None

    def test_lookup_returns_none_without_reader(self, mock_db):
        """Test that lookup returns None gracefully when no reader"""
        with patch("app.services.geolocation.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            service = GeoLocationService(mock_db, "/nonexistent/GeoLite2-City.mmdb")

        result = service.lookup_ip("8.8.8.8")
        assert result is None

    def test_bulk_lookup_returns_empty_without_reader(self, mock_db):
        """Test bulk lookup returns empty dict without reader"""
        with patch("app.services.geolocation.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            service = GeoLocationService(mock_db, "/nonexistent/GeoLite2-City.mmdb")

        # No cached entries either
        mock_db.query.return_value.filter.return_value.first.return_value = None

        results = service.lookup_ips_bulk(["1.1.1.1", "2.2.2.2"], use_cache=False)
        assert results == {}

    def test_cache_stats_reflects_no_reader(self, mock_db):
        """Test cache stats shows database_loaded=False when no reader"""
        with patch("app.services.geolocation.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            service = GeoLocationService(mock_db, "/nonexistent/GeoLite2-City.mmdb")

        mock_db.query.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        stats = service.get_cache_stats()
        assert stats["database_loaded"] is False

    def test_address_not_found_returns_none(self, mock_db):
        """Test that AddressNotFoundError returns None gracefully"""
        import geoip2.errors

        with patch("app.services.geolocation.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("geoip2.database.Reader") as mock_reader_cls:
                mock_reader = Mock()
                mock_reader.city.side_effect = geoip2.errors.AddressNotFoundError("not found")
                mock_reader_cls.return_value = mock_reader
                service = GeoLocationService(mock_db, "/fake/path.mmdb")

        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = service.lookup_ip("192.168.1.1", use_cache=True)
        assert result is None
