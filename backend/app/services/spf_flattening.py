"""
SPF Flattening Service.

Resolves include mechanisms to IP addresses to reduce DNS lookups.
SPF has a 10 DNS lookup limit, which can be exceeded with many includes.
"""

import dns.resolver
import dns.exception
import logging
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SPFMechanism(str, Enum):
    """SPF mechanism types"""
    ALL = "all"
    INCLUDE = "include"
    A = "a"
    MX = "mx"
    PTR = "ptr"
    IP4 = "ip4"
    IP6 = "ip6"
    EXISTS = "exists"
    REDIRECT = "redirect"


@dataclass
class SPFAnalysis:
    """Analysis of an SPF record"""
    domain: str
    original_record: str
    dns_lookups: int
    exceeds_limit: bool
    mechanisms: List[Dict[str, Any]]
    includes: List[str]
    ip4_addresses: List[str]
    ip6_addresses: List[str]
    errors: List[str]
    warnings: List[str]


@dataclass
class FlattenedSPF:
    """Flattened SPF record"""
    domain: str
    original_record: str
    original_lookups: int
    flattened_record: str
    flattened_lookups: int
    ip4_addresses: List[str]
    ip6_addresses: List[str]
    unresolved_includes: List[str]
    warnings: List[str]


class SPFFlatteningService:
    """Service for SPF record analysis and flattening"""

    MAX_DNS_LOOKUPS = 10
    MAX_RECURSION_DEPTH = 10

    def __init__(self):
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 5
        self.resolver.lifetime = 10

    def analyze_spf(self, domain: str) -> SPFAnalysis:
        """
        Analyze an SPF record for a domain.

        Args:
            domain: Domain to analyze

        Returns:
            SPFAnalysis with details about the record
        """
        errors = []
        warnings = []

        # Get SPF record
        spf_record = self._get_spf_record(domain)
        if not spf_record:
            return SPFAnalysis(
                domain=domain,
                original_record="",
                dns_lookups=0,
                exceeds_limit=False,
                mechanisms=[],
                includes=[],
                ip4_addresses=[],
                ip6_addresses=[],
                errors=["No SPF record found"],
                warnings=[],
            )

        # Parse mechanisms
        mechanisms = self._parse_spf(spf_record)

        # Count DNS lookups
        lookup_count = self._count_lookups(mechanisms)

        # Extract includes and IPs
        includes = [m["value"] for m in mechanisms if m["type"] == "include"]
        ip4s = [m["value"] for m in mechanisms if m["type"] == "ip4"]
        ip6s = [m["value"] for m in mechanisms if m["type"] == "ip6"]

        # Check limits
        if lookup_count > self.MAX_DNS_LOOKUPS:
            errors.append(f"SPF record exceeds {self.MAX_DNS_LOOKUPS} DNS lookup limit ({lookup_count} lookups)")
        elif lookup_count > 7:
            warnings.append(f"SPF record uses {lookup_count}/10 DNS lookups")

        # Check for deprecated ptr
        if any(m["type"] == "ptr" for m in mechanisms):
            warnings.append("'ptr' mechanism is deprecated and should be avoided")

        return SPFAnalysis(
            domain=domain,
            original_record=spf_record,
            dns_lookups=lookup_count,
            exceeds_limit=lookup_count > self.MAX_DNS_LOOKUPS,
            mechanisms=mechanisms,
            includes=includes,
            ip4_addresses=ip4s,
            ip6_addresses=ip6s,
            errors=errors,
            warnings=warnings,
        )

    def flatten_spf(
        self,
        domain: str,
        keep_includes: Optional[List[str]] = None,
    ) -> FlattenedSPF:
        """
        Flatten an SPF record by resolving includes to IP addresses.

        Args:
            domain: Domain to flatten
            keep_includes: List of includes to keep (not flatten)

        Returns:
            FlattenedSPF with flattened record
        """
        keep_includes = keep_includes or []
        warnings = []

        # Get original record
        spf_record = self._get_spf_record(domain)
        if not spf_record:
            return FlattenedSPF(
                domain=domain,
                original_record="",
                original_lookups=0,
                flattened_record="",
                flattened_lookups=0,
                ip4_addresses=[],
                ip6_addresses=[],
                unresolved_includes=[],
                warnings=["No SPF record found"],
            )

        # Parse original
        mechanisms = self._parse_spf(spf_record)
        original_lookups = self._count_lookups(mechanisms)

        # Collect all IPs recursively
        all_ip4s: Set[str] = set()
        all_ip6s: Set[str] = set()
        unresolved: List[str] = []

        for mech in mechanisms:
            if mech["type"] == "ip4":
                all_ip4s.add(mech["value"])
            elif mech["type"] == "ip6":
                all_ip6s.add(mech["value"])
            elif mech["type"] == "include":
                include_domain = mech["value"]
                if include_domain in keep_includes:
                    unresolved.append(include_domain)
                else:
                    # Resolve include
                    ip4s, ip6s, errors = self._resolve_include(include_domain)
                    all_ip4s.update(ip4s)
                    all_ip6s.update(ip6s)
                    if errors:
                        unresolved.append(include_domain)
                        warnings.extend(errors)
            elif mech["type"] in ["a", "mx"]:
                # Resolve A/MX
                ips = self._resolve_a_mx(domain if mech["value"] == "" else mech["value"], mech["type"])
                all_ip4s.update(ips)

        # Build flattened record
        parts = ["v=spf1"]

        # Add resolved IPs
        for ip in sorted(all_ip4s):
            parts.append(f"ip4:{ip}")
        for ip in sorted(all_ip6s):
            parts.append(f"ip6:{ip}")

        # Add kept includes
        for inc in unresolved:
            parts.append(f"include:{inc}")

        # Get all mechanism
        all_mech = next((m for m in mechanisms if m["type"] == "all"), None)
        if all_mech:
            parts.append(f"{all_mech['qualifier']}all")
        else:
            parts.append("~all")

        flattened_record = " ".join(parts)
        flattened_lookups = len(unresolved)  # Only kept includes count

        # Check length
        if len(flattened_record) > 255:
            warnings.append(f"Flattened record exceeds 255 characters ({len(flattened_record)})")

        return FlattenedSPF(
            domain=domain,
            original_record=spf_record,
            original_lookups=original_lookups,
            flattened_record=flattened_record,
            flattened_lookups=flattened_lookups,
            ip4_addresses=sorted(list(all_ip4s)),
            ip6_addresses=sorted(list(all_ip6s)),
            unresolved_includes=unresolved,
            warnings=warnings,
        )

    def _get_spf_record(self, domain: str) -> Optional[str]:
        """Get SPF TXT record for domain"""
        try:
            answers = self.resolver.resolve(domain, 'TXT')
            for rdata in answers:
                txt = rdata.to_text().strip('"')
                if txt.startswith("v=spf1"):
                    return txt
        except Exception as e:
            logger.debug(f"Failed to get SPF for {domain}: {e}")
        return None

    def _parse_spf(self, record: str) -> List[Dict[str, Any]]:
        """Parse SPF record into mechanisms"""
        mechanisms = []
        parts = record.split()

        for part in parts[1:]:  # Skip v=spf1
            qualifier = "+"
            if part[0] in "+-~?":
                qualifier = part[0]
                part = part[1:]

            if ":" in part:
                mtype, value = part.split(":", 1)
            elif "=" in part:
                mtype, value = part.split("=", 1)
            else:
                mtype = part
                value = ""

            mechanisms.append({
                "type": mtype.lower(),
                "value": value,
                "qualifier": qualifier,
            })

        return mechanisms

    def _count_lookups(self, mechanisms: List[Dict]) -> int:
        """Count DNS lookups required"""
        count = 0
        lookup_types = {"include", "a", "mx", "ptr", "exists", "redirect"}

        for mech in mechanisms:
            if mech["type"] in lookup_types:
                count += 1

        return count

    def _resolve_include(
        self,
        domain: str,
        depth: int = 0,
    ) -> tuple[Set[str], Set[str], List[str]]:
        """Recursively resolve include to IPs"""
        if depth > self.MAX_RECURSION_DEPTH:
            return set(), set(), [f"Max recursion depth reached for {domain}"]

        ip4s: Set[str] = set()
        ip6s: Set[str] = set()
        errors: List[str] = []

        spf = self._get_spf_record(domain)
        if not spf:
            return set(), set(), [f"Could not resolve SPF for {domain}"]

        mechanisms = self._parse_spf(spf)

        for mech in mechanisms:
            if mech["type"] == "ip4":
                ip4s.add(mech["value"])
            elif mech["type"] == "ip6":
                ip6s.add(mech["value"])
            elif mech["type"] == "include":
                nested_ip4s, nested_ip6s, nested_errors = self._resolve_include(
                    mech["value"], depth + 1
                )
                ip4s.update(nested_ip4s)
                ip6s.update(nested_ip6s)
                errors.extend(nested_errors)
            elif mech["type"] in ["a", "mx"]:
                ips = self._resolve_a_mx(
                    domain if mech["value"] == "" else mech["value"],
                    mech["type"]
                )
                ip4s.update(ips)

        return ip4s, ip6s, errors

    def _resolve_a_mx(self, domain: str, record_type: str) -> Set[str]:
        """Resolve A or MX records to IPs"""
        ips: Set[str] = set()

        try:
            if record_type == "mx":
                mx_answers = self.resolver.resolve(domain, 'MX')
                for mx in mx_answers:
                    mx_host = str(mx.exchange).rstrip('.')
                    try:
                        a_answers = self.resolver.resolve(mx_host, 'A')
                        for a in a_answers:
                            ips.add(str(a))
                    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout, Exception) as e:
                        logger.debug("Failed to resolve A records for %s: %s", mx_host, e)
            else:  # a
                a_answers = self.resolver.resolve(domain, 'A')
                for a in a_answers:
                    ips.add(str(a))
        except Exception as e:
            logger.debug(f"Failed to resolve {record_type} for {domain}: {e}")

        return ips
