"""
DMARC Record Generator Service.

Provides wizard-style generation of DMARC, SPF, and DKIM DNS records
with validation and best practice recommendations.
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class DMARCPolicy(str, Enum):
    """DMARC policy options"""
    NONE = "none"           # Monitor only
    QUARANTINE = "quarantine"  # Send to spam
    REJECT = "reject"       # Reject entirely


class AlignmentMode(str, Enum):
    """DKIM/SPF alignment mode"""
    RELAXED = "r"  # Subdomain match allowed
    STRICT = "s"   # Exact domain match required


class ReportFormat(str, Enum):
    """DMARC report format"""
    AFRF = "afrf"  # Aggregate Failure Report Format (default)


@dataclass
class DMARCRecord:
    """Generated DMARC record"""
    domain: str
    record_name: str  # e.g., _dmarc
    record_type: str  # TXT
    record_value: str  # Full DMARC string
    ttl: int = 3600


@dataclass
class SPFRecord:
    """Generated SPF record"""
    domain: str
    record_name: str  # @ or subdomain
    record_type: str  # TXT
    record_value: str  # Full SPF string
    ttl: int = 3600


@dataclass
class ValidationResult:
    """Result of record validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]


class DMARCGeneratorService:
    """Service for generating DNS records"""

    # Maximum lengths
    MAX_SPF_LOOKUPS = 10
    MAX_TXT_LENGTH = 255

    def generate_dmarc(
        self,
        domain: str,
        policy: DMARCPolicy = DMARCPolicy.NONE,
        subdomain_policy: Optional[DMARCPolicy] = None,
        pct: int = 100,
        rua: Optional[List[str]] = None,  # Aggregate report URIs
        ruf: Optional[List[str]] = None,  # Forensic report URIs
        adkim: AlignmentMode = AlignmentMode.RELAXED,
        aspf: AlignmentMode = AlignmentMode.RELAXED,
        fo: str = "0",  # Failure reporting options
        rf: ReportFormat = ReportFormat.AFRF,
        ri: int = 86400,  # Report interval (seconds)
    ) -> DMARCRecord:
        """
        Generate a DMARC record.

        Args:
            domain: Domain name
            policy: Main policy (none, quarantine, reject)
            subdomain_policy: Subdomain policy (defaults to main policy)
            pct: Percentage of messages to apply policy to (1-100)
            rua: Aggregate report recipient URIs
            ruf: Forensic report recipient URIs
            adkim: DKIM alignment mode
            aspf: SPF alignment mode
            fo: Failure reporting options
            rf: Report format
            ri: Report interval in seconds

        Returns:
            DMARCRecord with generated values
        """
        parts = ["v=DMARC1", f"p={policy.value}"]

        # Add subdomain policy if different
        if subdomain_policy and subdomain_policy != policy:
            parts.append(f"sp={subdomain_policy.value}")

        # Add percentage if not 100%
        if pct < 100:
            parts.append(f"pct={pct}")

        # Add aggregate report URIs
        if rua:
            rua_str = ",".join(f"mailto:{uri}" if "@" in uri and not uri.startswith("mailto:") else uri for uri in rua)
            parts.append(f"rua={rua_str}")

        # Add forensic report URIs
        if ruf:
            ruf_str = ",".join(f"mailto:{uri}" if "@" in uri and not uri.startswith("mailto:") else uri for uri in ruf)
            parts.append(f"ruf={ruf_str}")

        # Add alignment modes if not default
        if adkim == AlignmentMode.STRICT:
            parts.append(f"adkim={adkim.value}")
        if aspf == AlignmentMode.STRICT:
            parts.append(f"aspf={aspf.value}")

        # Add failure reporting options if not default
        if fo != "0":
            parts.append(f"fo={fo}")

        # Report interval if not default (24 hours)
        if ri != 86400:
            parts.append(f"ri={ri}")

        record_value = "; ".join(parts)

        return DMARCRecord(
            domain=domain,
            record_name=f"_dmarc.{domain}",
            record_type="TXT",
            record_value=record_value,
        )

    def generate_spf(
        self,
        domain: str,
        include: Optional[List[str]] = None,
        ip4: Optional[List[str]] = None,
        ip6: Optional[List[str]] = None,
        a: bool = False,
        mx: bool = False,
        ptr: bool = False,  # Deprecated
        exists: Optional[str] = None,
        redirect: Optional[str] = None,
        all_mechanism: str = "~all",  # ~all, -all, ?all, +all
    ) -> SPFRecord:
        """
        Generate an SPF record.

        Args:
            domain: Domain name
            include: Domains to include (e.g., _spf.google.com)
            ip4: IPv4 addresses/ranges
            ip6: IPv6 addresses/ranges
            a: Include domain's A record
            mx: Include domain's MX records
            ptr: Include PTR mechanism (deprecated)
            exists: Exists mechanism
            redirect: Redirect to another domain
            all_mechanism: Final all mechanism

        Returns:
            SPFRecord with generated values
        """
        parts = ["v=spf1"]

        # Add mechanisms
        if a:
            parts.append("a")
        if mx:
            parts.append("mx")

        # Add IP addresses
        if ip4:
            for ip in ip4:
                parts.append(f"ip4:{ip}")
        if ip6:
            for ip in ip6:
                parts.append(f"ip6:{ip}")

        # Add includes
        if include:
            for inc in include:
                parts.append(f"include:{inc}")

        # Add exists
        if exists:
            parts.append(f"exists:{exists}")

        # Add redirect or all
        if redirect:
            parts.append(f"redirect={redirect}")
        else:
            parts.append(all_mechanism)

        record_value = " ".join(parts)

        return SPFRecord(
            domain=domain,
            record_name=domain,
            record_type="TXT",
            record_value=record_value,
        )

    def validate_dmarc(self, record_value: str) -> ValidationResult:
        """Validate a DMARC record string"""
        errors = []
        warnings = []
        suggestions = []

        # Check version
        if not record_value.startswith("v=DMARC1"):
            errors.append("DMARC record must start with 'v=DMARC1'")

        # Check for policy
        if "p=" not in record_value:
            errors.append("DMARC record must include a policy (p=)")

        # Parse policy
        policy_match = re.search(r"p=(none|quarantine|reject)", record_value.lower())
        if policy_match:
            policy = policy_match.group(1)
            if policy == "none":
                warnings.append("Policy 'none' only monitors - consider 'quarantine' or 'reject' for protection")
        else:
            errors.append("Invalid policy value. Must be 'none', 'quarantine', or 'reject'")

        # Check for report URI
        if "rua=" not in record_value:
            suggestions.append("Consider adding rua= to receive aggregate reports")

        # Check percentage
        pct_match = re.search(r"pct=(\d+)", record_value)
        if pct_match:
            pct = int(pct_match.group(1))
            if pct < 100:
                warnings.append(f"Only {pct}% of messages will have policy applied")
            if pct < 1 or pct > 100:
                errors.append("pct must be between 1 and 100")

        # Check length
        if len(record_value) > self.MAX_TXT_LENGTH:
            errors.append(f"Record exceeds maximum TXT length of {self.MAX_TXT_LENGTH} characters")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def validate_spf(self, record_value: str) -> ValidationResult:
        """Validate an SPF record string"""
        errors = []
        warnings = []
        suggestions = []

        # Check version
        if not record_value.startswith("v=spf1"):
            errors.append("SPF record must start with 'v=spf1'")

        # Count DNS lookups
        lookups = 0
        lookups += len(re.findall(r"include:", record_value))
        lookups += len(re.findall(r"\ba\b", record_value))
        lookups += len(re.findall(r"\bmx\b", record_value))
        lookups += len(re.findall(r"redirect=", record_value))
        lookups += len(re.findall(r"exists:", record_value))

        if lookups > self.MAX_SPF_LOOKUPS:
            errors.append(f"SPF record exceeds {self.MAX_SPF_LOOKUPS} DNS lookup limit ({lookups} lookups)")
        elif lookups > 7:
            warnings.append(f"SPF record uses {lookups}/10 DNS lookups. Consider optimization.")

        # Check for ptr (deprecated)
        if "ptr" in record_value.lower():
            warnings.append("'ptr' mechanism is deprecated and should be avoided")

        # Check for +all (dangerous)
        if "+all" in record_value:
            errors.append("'+all' allows any server to send email - this is insecure")

        # Check for ?all
        if "?all" in record_value:
            warnings.append("'?all' provides no protection - consider '~all' or '-all'")

        # Check length
        if len(record_value) > self.MAX_TXT_LENGTH:
            errors.append(f"Record exceeds maximum TXT length of {self.MAX_TXT_LENGTH} characters")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def get_policy_recommendation(
        self,
        has_existing_dmarc: bool,
        current_policy: Optional[str],
        pass_rate: float,
        days_monitoring: int,
    ) -> Dict[str, Any]:
        """
        Get policy recommendation based on current state.

        Args:
            has_existing_dmarc: Whether domain has DMARC record
            current_policy: Current DMARC policy (none, quarantine, reject)
            pass_rate: Current DMARC pass rate (0-100)
            days_monitoring: Days spent at current policy

        Returns:
            Recommendation with suggested policy and reasoning
        """
        if not has_existing_dmarc:
            return {
                "recommended_policy": "none",
                "pct": 100,
                "reasoning": "Start with 'none' policy to monitor email flow without affecting delivery",
                "next_steps": [
                    "Add DMARC record with p=none",
                    "Configure rua= to receive aggregate reports",
                    "Monitor for at least 2-4 weeks",
                    "Identify and authorize legitimate senders",
                ]
            }

        if current_policy == "none":
            if pass_rate >= 99 and days_monitoring >= 14:
                return {
                    "recommended_policy": "quarantine",
                    "pct": 10,
                    "reasoning": f"High pass rate ({pass_rate:.1f}%) after {days_monitoring} days - ready to move to quarantine",
                    "next_steps": [
                        "Update to p=quarantine pct=10",
                        "Monitor for issues with legitimate mail",
                        "Gradually increase pct to 100",
                        "Then consider moving to reject",
                    ]
                }
            elif pass_rate >= 95 and days_monitoring >= 30:
                return {
                    "recommended_policy": "quarantine",
                    "pct": 5,
                    "reasoning": f"Good pass rate ({pass_rate:.1f}%) - start with cautious quarantine",
                    "next_steps": [
                        "Update to p=quarantine pct=5",
                        "Investigate remaining failures",
                        "Gradually increase percentage",
                    ]
                }
            else:
                return {
                    "recommended_policy": "none",
                    "pct": 100,
                    "reasoning": f"Continue monitoring - pass rate is {pass_rate:.1f}% (need >95%)",
                    "next_steps": [
                        "Keep monitoring with p=none",
                        "Investigate and fix SPF/DKIM failures",
                        "Ensure all legitimate senders are authorized",
                    ]
                }

        elif current_policy == "quarantine":
            if pass_rate >= 99 and days_monitoring >= 14:
                return {
                    "recommended_policy": "reject",
                    "pct": 10,
                    "reasoning": f"Excellent pass rate ({pass_rate:.1f}%) at quarantine - ready for reject",
                    "next_steps": [
                        "Update to p=reject pct=10",
                        "Monitor closely for any issues",
                        "Gradually increase to 100%",
                    ]
                }
            else:
                return {
                    "recommended_policy": "quarantine",
                    "pct": 100,
                    "reasoning": f"Continue at quarantine - pass rate is {pass_rate:.1f}%",
                    "next_steps": [
                        "Keep monitoring at quarantine",
                        "Investigate any remaining failures",
                        "Move to reject when pass rate is >99%",
                    ]
                }

        else:  # reject
            return {
                "recommended_policy": "reject",
                "pct": 100,
                "reasoning": "Already at maximum protection with p=reject",
                "next_steps": [
                    "Continue monitoring aggregate reports",
                    "Investigate any new failures",
                    "Ensure strict alignment if not already",
                ]
            }

    def generate_wizard_steps(self) -> List[Dict[str, Any]]:
        """Generate wizard step definitions"""
        return [
            {
                "step": 1,
                "title": "Domain Selection",
                "description": "Enter the domain you want to protect",
                "fields": ["domain"],
            },
            {
                "step": 2,
                "title": "Policy Selection",
                "description": "Choose how to handle messages that fail DMARC",
                "fields": ["policy", "subdomain_policy", "pct"],
                "options": {
                    "policy": [
                        {"value": "none", "label": "None (Monitor Only)", "description": "No action on failures, just receive reports"},
                        {"value": "quarantine", "label": "Quarantine", "description": "Send failing messages to spam/junk"},
                        {"value": "reject", "label": "Reject", "description": "Block failing messages entirely"},
                    ]
                }
            },
            {
                "step": 3,
                "title": "Report Configuration",
                "description": "Configure where to receive DMARC reports",
                "fields": ["rua", "ruf"],
            },
            {
                "step": 4,
                "title": "Alignment Settings",
                "description": "Configure DKIM and SPF alignment",
                "fields": ["adkim", "aspf"],
                "advanced": True,
            },
            {
                "step": 5,
                "title": "Review & Generate",
                "description": "Review your settings and generate the DNS record",
                "fields": [],
            },
        ]
