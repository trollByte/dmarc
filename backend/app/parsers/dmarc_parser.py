"""
DMARC Aggregate Report XML Parser

Pure parser with no database dependencies.
Handles decompression (.gz, .zip) and XML parsing.
"""
import gzip
import zipfile
import io
import xmltodict
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class DmarcParseError(Exception):
    """Raised when DMARC XML parsing fails"""
    pass


class ReportMetadata(BaseModel):
    """Report metadata"""
    org_name: str
    email: Optional[str] = None
    extra_contact_info: Optional[str] = None
    report_id: str
    date_begin: datetime
    date_end: datetime


class PolicyPublished(BaseModel):
    """Published DMARC policy"""
    domain: str
    adkim: Optional[str] = None  # DKIM alignment mode
    aspf: Optional[str] = None   # SPF alignment mode
    p: str                        # Policy for domain
    sp: Optional[str] = None      # Policy for subdomains
    pct: Optional[int] = 100      # Percentage of messages to filter


class AuthResult(BaseModel):
    """Authentication result (DKIM or SPF)"""
    domain: Optional[str] = None
    result: Optional[str] = None
    selector: Optional[str] = None  # DKIM only
    scope: Optional[str] = None     # SPF only


class PolicyEvaluated(BaseModel):
    """Policy evaluation for a record"""
    disposition: Optional[str] = None
    dkim: Optional[str] = None
    spf: Optional[str] = None


class Identifiers(BaseModel):
    """Identifiers for a record"""
    header_from: Optional[str] = None
    envelope_from: Optional[str] = None
    envelope_to: Optional[str] = None


class DmarcRecord(BaseModel):
    """Individual DMARC record from a report"""
    source_ip: str
    count: int
    policy_evaluated: PolicyEvaluated
    identifiers: Identifiers
    auth_results_dkim: List[AuthResult] = Field(default_factory=list)
    auth_results_spf: List[AuthResult] = Field(default_factory=list)


class DmarcReport(BaseModel):
    """Complete DMARC aggregate report"""
    metadata: ReportMetadata
    policy_published: PolicyPublished
    records: List[DmarcRecord]


def decompress_file(data: bytes, filename: str) -> bytes:
    """
    Decompress file if needed (.gz or .zip)

    Uses magic bytes to detect actual content type, not just filename extension.
    Some files have .gz extension but contain plain XML.

    Args:
        data: File content as bytes
        filename: Original filename (used for error messages)

    Returns:
        Decompressed XML data as bytes

    Raises:
        DmarcParseError: If decompression fails
    """
    if not data:
        raise DmarcParseError(f"Empty file: {filename}")

    try:
        # Check magic bytes to detect actual content type
        # Gzip: 1f 8b
        # Zip: 50 4b (PK)
        # XML: 3c (< character) or starts with whitespace then <

        if data[:2] == b'\x1f\x8b':
            # Actual gzip file
            return gzip.decompress(data)
        elif data[:2] == b'PK':
            # Actual zip file
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = zf.namelist()
                if not names:
                    raise DmarcParseError("Empty zip file")
                # Read first file in zip
                return zf.read(names[0])
        else:
            # Assume raw XML (may start with <, whitespace, or BOM)
            return data
    except Exception as e:
        raise DmarcParseError(f"Failed to decompress {filename}: {str(e)}")


def parse_auth_results(auth_results: Any) -> tuple[List[AuthResult], List[AuthResult]]:
    """
    Parse authentication results for DKIM and SPF

    Returns:
        Tuple of (dkim_results, spf_results)
    """
    dkim_results = []
    spf_results = []

    if not auth_results:
        return dkim_results, spf_results

    # Handle DKIM results
    dkim = auth_results.get('dkim')
    if dkim:
        # Can be a single dict or list of dicts
        dkim_list = dkim if isinstance(dkim, list) else [dkim]
        for d in dkim_list:
            if d:
                dkim_results.append(AuthResult(
                    domain=d.get('domain'),
                    result=d.get('result'),
                    selector=d.get('selector')
                ))

    # Handle SPF results
    spf = auth_results.get('spf')
    if spf:
        # Can be a single dict or list of dicts
        spf_list = spf if isinstance(spf, list) else [spf]
        for s in spf_list:
            if s:
                spf_results.append(AuthResult(
                    domain=s.get('domain'),
                    result=s.get('result'),
                    scope=s.get('scope')
                ))

    return dkim_results, spf_results


def parse_xml(xml_data: bytes) -> DmarcReport:
    """
    Parse DMARC aggregate report XML

    Args:
        xml_data: XML content as bytes

    Returns:
        Parsed DmarcReport object

    Raises:
        DmarcParseError: If XML is invalid or missing required fields
    """
    try:
        data = xmltodict.parse(xml_data)
    except Exception as e:
        raise DmarcParseError(f"Failed to parse XML: {str(e)}")

    feedback = data.get('feedback')
    if not feedback:
        raise DmarcParseError("Invalid DMARC XML: missing 'feedback' root element")

    # Parse metadata
    meta = feedback.get('report_metadata', {})
    if not meta:
        raise DmarcParseError("Missing report_metadata")

    date_range = meta.get('date_range', {})
    try:
        metadata = ReportMetadata(
            org_name=meta.get('org_name', 'Unknown'),
            email=meta.get('email'),
            extra_contact_info=meta.get('extra_contact_info'),
            report_id=meta.get('report_id', ''),
            date_begin=datetime.fromtimestamp(int(date_range.get('begin', 0))),
            date_end=datetime.fromtimestamp(int(date_range.get('end', 0)))
        )
    except (ValueError, TypeError) as e:
        raise DmarcParseError(f"Invalid metadata: {str(e)}")

    # Parse policy
    policy = feedback.get('policy_published', {})
    if not policy:
        raise DmarcParseError("Missing policy_published")

    try:
        policy_published = PolicyPublished(
            domain=policy.get('domain', ''),
            adkim=policy.get('adkim'),
            aspf=policy.get('aspf'),
            p=policy.get('p', 'none'),
            sp=policy.get('sp'),
            pct=int(policy.get('pct', 100))
        )
    except (ValueError, TypeError) as e:
        raise DmarcParseError(f"Invalid policy: {str(e)}")

    # Parse records
    records_data = feedback.get('record', [])
    # Ensure it's a list
    if not isinstance(records_data, list):
        records_data = [records_data]

    records = []
    for rec in records_data:
        if not rec:
            continue

        try:
            row = rec.get('row', {})
            source_ip = row.get('source_ip', '')
            count = int(row.get('count', 0))

            # Policy evaluated
            policy_eval = row.get('policy_evaluated', {})
            policy_evaluated = PolicyEvaluated(
                disposition=policy_eval.get('disposition'),
                dkim=policy_eval.get('dkim'),
                spf=policy_eval.get('spf')
            )

            # Identifiers
            ids = rec.get('identifiers', {})
            identifiers = Identifiers(
                header_from=ids.get('header_from'),
                envelope_from=ids.get('envelope_from'),
                envelope_to=ids.get('envelope_to')
            )

            # Auth results
            auth_results = rec.get('auth_results', {})
            dkim_results, spf_results = parse_auth_results(auth_results)

            records.append(DmarcRecord(
                source_ip=source_ip,
                count=count,
                policy_evaluated=policy_evaluated,
                identifiers=identifiers,
                auth_results_dkim=dkim_results,
                auth_results_spf=spf_results
            ))
        except (ValueError, TypeError) as e:
            # Log warning but continue processing other records
            import logging
            logging.warning(f"Skipping invalid record: {str(e)}")
            continue

    return DmarcReport(
        metadata=metadata,
        policy_published=policy_published,
        records=records
    )


def parse_dmarc_report(file_content: bytes, filename: str) -> DmarcReport:
    """
    Main entry point for parsing a DMARC report file

    Args:
        file_content: File content as bytes
        filename: Original filename

    Returns:
        Parsed DmarcReport object

    Raises:
        DmarcParseError: If parsing fails
    """
    # Decompress if needed
    xml_data = decompress_file(file_content, filename)

    # Parse XML
    return parse_xml(xml_data)
