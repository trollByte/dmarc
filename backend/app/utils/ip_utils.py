"""IP address utilities for filtering"""
import ipaddress
from typing import Optional, Union


def parse_ip_range(ip_range: str) -> Optional[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """
    Parse CIDR notation to IP network object

    Args:
        ip_range: CIDR notation string (e.g., "192.168.1.0/24")

    Returns:
        IPv4Network or IPv6Network object, or None if invalid
    """
    try:
        return ipaddress.ip_network(ip_range, strict=False)
    except ValueError:
        return None


def ip_in_range(ip: str, ip_range: str) -> bool:
    """
    Check if IP address is within CIDR range

    Args:
        ip: IP address string
        ip_range: CIDR notation string (e.g., "192.168.1.0/24")

    Returns:
        True if IP is in range, False otherwise
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        network = ipaddress.ip_network(ip_range, strict=False)
        return ip_obj in network
    except ValueError:
        return False


def is_valid_ip(ip: str) -> bool:
    """
    Validate IP address format

    Args:
        ip: IP address string

    Returns:
        True if valid IPv4 or IPv6 address, False otherwise
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False
