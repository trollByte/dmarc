"""
IP Geolocation service using MaxMind GeoLite2.

Features:
- Offline IP geolocation using MaxMind GeoLite2 City database
- 90-day database cache to minimize lookups
- Bulk IP lookup for efficiency
- Monthly database auto-update (via Celery task)
"""

import logging
import geoip2.database
import geoip2.errors
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session

from app.models import GeoLocationCache

logger = logging.getLogger(__name__)


class GeoLocationService:
    """
    IP geolocation service using MaxMind GeoLite2.

    Provides offline IP-to-location mapping with database caching.
    """

    def __init__(self, db: Session, maxmind_db_path: str = "/app/data/GeoLite2-City.mmdb"):
        """
        Initialize geolocation service.

        Args:
            db: Database session
            maxmind_db_path: Path to MaxMind GeoLite2 City database file

        Raises:
            FileNotFoundError: If MaxMind database file not found
        """
        self.db = db
        self.maxmind_db_path = Path(maxmind_db_path)

        # Check if database file exists
        if not self.maxmind_db_path.exists():
            logger.warning(
                f"MaxMind database not found at {maxmind_db_path}. "
                "Geolocation features will be unavailable. "
                "Download GeoLite2-City.mmdb from https://dev.maxmind.com/geoip/geolite2-free-geolocation-data"
            )
            self.reader = None
        else:
            try:
                self.reader = geoip2.database.Reader(str(self.maxmind_db_path))
                logger.info(f"MaxMind database loaded from {maxmind_db_path}")
            except Exception as e:
                logger.error(f"Failed to load MaxMind database: {e}")
                self.reader = None

    def __del__(self):
        """Close MaxMind database reader on cleanup"""
        if self.reader:
            try:
                self.reader.close()
            except:
                pass

    # ==================== Single IP Lookup ====================

    def lookup_ip(self, ip_address: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Lookup geolocation for single IP address.

        Args:
            ip_address: IP address (IPv4 or IPv6)
            use_cache: Use database cache (default: True)

        Returns:
            Dictionary with geolocation data or None if not found
        """
        if not self.reader:
            logger.debug("MaxMind database not available")
            return None

        # Check cache first
        if use_cache:
            cached = self._get_from_cache(ip_address)
            if cached:
                return self._cache_to_dict(cached)

        # Perform MaxMind lookup
        try:
            response = self.reader.city(ip_address)

            geo_data = {
                "ip_address": ip_address,
                "country_code": response.country.iso_code,
                "country_name": response.country.name,
                "city_name": response.city.name,
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
                "timezone": response.location.time_zone,
                "continent_code": response.continent.code,
                "continent_name": response.continent.name,
                "asn": None,  # Not available in free GeoLite2 City
                "asn_organization": None,
                "isp": None,
            }

            # Cache result
            if use_cache:
                self._save_to_cache(geo_data)

            logger.debug(f"Geolocation found for {ip_address}: {geo_data['country_code']}")
            return geo_data

        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"IP address not found in MaxMind database: {ip_address}")
            return None
        except Exception as e:
            logger.error(f"Error looking up IP {ip_address}: {e}")
            return None

    # ==================== Bulk IP Lookup ====================

    def lookup_ips_bulk(
        self,
        ip_addresses: List[str],
        use_cache: bool = True
    ) -> Dict[str, Optional[Dict]]:
        """
        Bulk lookup geolocation for multiple IP addresses.

        More efficient than individual lookups.

        Args:
            ip_addresses: List of IP addresses
            use_cache: Use database cache (default: True)

        Returns:
            Dictionary mapping IP -> geolocation data
        """
        results = {}
        uncached_ips = []

        # Check cache first
        if use_cache:
            for ip in ip_addresses:
                cached = self._get_from_cache(ip)
                if cached:
                    results[ip] = self._cache_to_dict(cached)
                else:
                    uncached_ips.append(ip)
        else:
            uncached_ips = ip_addresses

        # Lookup uncached IPs
        if uncached_ips and self.reader:
            for ip in uncached_ips:
                geo_data = self.lookup_ip(ip, use_cache=use_cache)
                results[ip] = geo_data

        logger.info(
            f"Bulk lookup complete: {len(results)} IPs processed, "
            f"{len(uncached_ips)} cache misses"
        )

        return results

    # ==================== Geographic Aggregation ====================

    def _aggregate_by_key(
        self,
        ip_addresses: List[str],
        key_extractor,
        use_cache: bool = True
    ) -> Dict[str, int]:
        """
        Aggregate IP geolocation data by a custom key.

        Args:
            ip_addresses: List of IP addresses
            key_extractor: Function that takes geo_data and returns a key (or None to skip)
            use_cache: Use database cache

        Returns:
            Dictionary mapping key -> count, sorted by count descending
        """
        geo_results = self.lookup_ips_bulk(ip_addresses, use_cache=use_cache)

        counts = {}
        for geo_data in geo_results.values():
            if geo_data:
                key = key_extractor(geo_data)
                if key:
                    counts[key] = counts.get(key, 0) + 1

        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def get_country_counts(
        self,
        ip_addresses: List[str],
        use_cache: bool = True
    ) -> Dict[str, int]:
        """
        Get count of IPs by country.

        Args:
            ip_addresses: List of IP addresses
            use_cache: Use database cache

        Returns:
            Dictionary mapping country_code -> count
        """
        return self._aggregate_by_key(
            ip_addresses,
            lambda geo: geo.get("country_code"),
            use_cache
        )

    def get_city_counts(
        self,
        ip_addresses: List[str],
        use_cache: bool = True
    ) -> Dict[str, int]:
        """
        Get count of IPs by city.

        Args:
            ip_addresses: List of IP addresses
            use_cache: Use database cache

        Returns:
            Dictionary mapping "City, Country" -> count
        """
        def city_key(geo):
            city = geo.get("city_name")
            country = geo.get("country_code")
            if city and country:
                return f"{city}, {country}"
            return None

        return self._aggregate_by_key(ip_addresses, city_key, use_cache)

    def get_coordinates(
        self,
        ip_addresses: List[str],
        use_cache: bool = True
    ) -> List[Tuple[float, float]]:
        """
        Get lat/lon coordinates for IPs (for map visualization).

        Args:
            ip_addresses: List of IP addresses
            use_cache: Use database cache

        Returns:
            List of (latitude, longitude) tuples
        """
        geo_results = self.lookup_ips_bulk(ip_addresses, use_cache=use_cache)

        coordinates = []
        for ip, geo_data in geo_results.items():
            if geo_data and geo_data.get("latitude") and geo_data.get("longitude"):
                coordinates.append((geo_data["latitude"], geo_data["longitude"]))

        return coordinates

    # ==================== Cache Management ====================

    def _get_from_cache(self, ip_address: str) -> Optional[GeoLocationCache]:
        """Get geolocation from cache if not expired"""
        cached = self.db.query(GeoLocationCache).filter(
            GeoLocationCache.ip_address == ip_address,
            GeoLocationCache.expires_at > datetime.utcnow()
        ).first()

        return cached

    def _save_to_cache(self, geo_data: Dict) -> None:
        """Save geolocation to cache"""
        # Check if already exists
        existing = self.db.query(GeoLocationCache).filter(
            GeoLocationCache.ip_address == geo_data["ip_address"]
        ).first()

        expires_at = datetime.utcnow() + timedelta(days=90)

        if existing:
            # Update existing
            for key, value in geo_data.items():
                if key != "ip_address":
                    setattr(existing, key, value)
            existing.expires_at = expires_at
        else:
            # Create new
            cache_entry = GeoLocationCache(
                ip_address=geo_data["ip_address"],
                country_code=geo_data.get("country_code"),
                country_name=geo_data.get("country_name"),
                city_name=geo_data.get("city_name"),
                latitude=geo_data.get("latitude"),
                longitude=geo_data.get("longitude"),
                timezone=geo_data.get("timezone"),
                continent_code=geo_data.get("continent_code"),
                continent_name=geo_data.get("continent_name"),
                asn=geo_data.get("asn"),
                asn_organization=geo_data.get("asn_organization"),
                isp=geo_data.get("isp"),
                expires_at=expires_at
            )
            self.db.add(cache_entry)

        self.db.commit()

    def _cache_to_dict(self, cache_entry: GeoLocationCache) -> Dict:
        """Convert cache entry to dictionary"""
        return {
            "ip_address": cache_entry.ip_address,
            "country_code": cache_entry.country_code,
            "country_name": cache_entry.country_name,
            "city_name": cache_entry.city_name,
            "latitude": cache_entry.latitude,
            "longitude": cache_entry.longitude,
            "timezone": cache_entry.timezone,
            "continent_code": cache_entry.continent_code,
            "continent_name": cache_entry.continent_name,
            "asn": cache_entry.asn,
            "asn_organization": cache_entry.asn_organization,
            "isp": cache_entry.isp,
        }

    def purge_expired_cache(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries purged
        """
        count = self.db.query(GeoLocationCache).filter(
            GeoLocationCache.expires_at < datetime.utcnow()
        ).delete()

        self.db.commit()

        logger.info(f"Purged {count} expired geolocation cache entries")
        return count

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.db.query(GeoLocationCache).count()
        expired = self.db.query(GeoLocationCache).filter(
            GeoLocationCache.expires_at < datetime.utcnow()
        ).count()

        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "database_loaded": self.reader is not None,
            "database_path": str(self.maxmind_db_path)
        }

    # ==================== Heatmap Generation ====================

    def generate_country_heatmap(
        self,
        ip_addresses: List[str],
        use_cache: bool = True
    ) -> Dict:
        """
        Generate country heatmap data for visualization.

        Args:
            ip_addresses: List of IP addresses
            use_cache: Use database cache

        Returns:
            Dictionary with heatmap data:
            {
                "countries": {
                    "US": {"count": 100, "name": "United States"},
                    "GB": {"count": 50, "name": "United Kingdom"},
                    ...
                },
                "max_count": 100,
                "total_ips": 150
            }
        """
        geo_results = self.lookup_ips_bulk(ip_addresses, use_cache=use_cache)

        countries = {}
        for ip, geo_data in geo_results.items():
            if geo_data and geo_data.get("country_code"):
                code = geo_data["country_code"]
                if code not in countries:
                    countries[code] = {
                        "count": 0,
                        "name": geo_data.get("country_name", code)
                    }
                countries[code]["count"] += 1

        max_count = max([c["count"] for c in countries.values()]) if countries else 0

        return {
            "countries": countries,
            "max_count": max_count,
            "total_ips": len(ip_addresses),
            "mapped_ips": sum(c["count"] for c in countries.values()),
            "unmapped_ips": len(ip_addresses) - sum(c["count"] for c in countries.values())
        }
