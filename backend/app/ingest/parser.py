import gzip
import zipfile
import io
import xmltodict
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.schemas import ReportCreate, RecordCreate


def decompress_attachment(data: bytes, filename: str) -> bytes:
    """
    Decompress gzip or zip compressed data

    Args:
        data: Compressed file data
        filename: Name of the file to determine compression type

    Returns:
        Decompressed bytes
    """
    filename_lower = filename.lower()

    try:
        if filename_lower.endswith('.gz'):
            return gzip.decompress(data)
        elif filename_lower.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # Get the first file in the zip
                names = zf.namelist()
                if not names:
                    raise ValueError("Empty zip file")
                return zf.read(names[0])
        else:
            # Assume uncompressed XML
            return data
    except Exception as e:
        raise ValueError(f"Failed to decompress file {filename}: {str(e)}")


def parse_dmarc_xml(xml_data: bytes) -> ReportCreate:
    """
    Parse DMARC aggregate report XML

    Args:
        xml_data: XML data as bytes

    Returns:
        ReportCreate object with parsed data
    """
    try:
        # Parse XML to dict
        data = xmltodict.parse(xml_data)
        feedback = data.get('feedback', {})

        if not feedback:
            raise ValueError("Invalid DMARC XML: missing 'feedback' root element")

        # Extract report metadata
        report_metadata = feedback.get('report_metadata', {})
        policy_published = feedback.get('policy_published', {})
        records_data = feedback.get('record', [])

        # Ensure records is a list
        if not isinstance(records_data, list):
            records_data = [records_data]

        # Parse report metadata
        report_id = report_metadata.get('report_id')
        org_name = report_metadata.get('org_name')
        email = report_metadata.get('email')
        extra_contact_info = report_metadata.get('extra_contact_info')

        # Parse date range
        date_range = report_metadata.get('date_range', {})
        date_begin = datetime.fromtimestamp(int(date_range.get('begin', 0)))
        date_end = datetime.fromtimestamp(int(date_range.get('end', 0)))

        # Parse policy published
        domain = policy_published.get('domain')
        adkim = policy_published.get('adkim', 'r')
        aspf = policy_published.get('aspf', 'r')
        p = policy_published.get('p')
        sp = policy_published.get('sp')
        pct = int(policy_published.get('pct', 100))

        # Validate required fields
        if not report_id:
            raise ValueError("Missing required field: report_id")
        if not org_name:
            raise ValueError("Missing required field: org_name")
        if not domain:
            raise ValueError("Missing required field: domain")

        # Parse records
        records = []
        for record in records_data:
            row = record.get('row', {})
            identifiers = record.get('identifiers', {})
            auth_results = record.get('auth_results', {})

            # Row data
            source_ip = row.get('source_ip')
            count = int(row.get('count', 0))

            policy_evaluated = row.get('policy_evaluated', {})
            disposition = policy_evaluated.get('disposition')
            dkim_result = policy_evaluated.get('dkim')
            spf_result = policy_evaluated.get('spf')

            # Identifiers
            envelope_to = identifiers.get('envelope_to')
            envelope_from = identifiers.get('envelope_from')
            header_from = identifiers.get('header_from')

            # Auth results - DKIM
            dkim_data = auth_results.get('dkim', {})
            if not isinstance(dkim_data, list):
                dkim_data = [dkim_data] if dkim_data else []

            dkim_domain = None
            dkim_selector = None
            dkim_auth_result = None
            if dkim_data and dkim_data[0]:
                dkim_domain = dkim_data[0].get('domain')
                dkim_selector = dkim_data[0].get('selector')
                dkim_auth_result = dkim_data[0].get('result')

            # Auth results - SPF
            spf_data = auth_results.get('spf', {})
            if not isinstance(spf_data, list):
                spf_data = [spf_data] if spf_data else []

            spf_domain = None
            spf_scope = None
            spf_auth_result = None
            if spf_data and spf_data[0]:
                spf_domain = spf_data[0].get('domain')
                spf_scope = spf_data[0].get('scope')
                spf_auth_result = spf_data[0].get('result')

            # Validate required record fields
            if not source_ip:
                continue  # Skip records without source IP

            records.append(RecordCreate(
                source_ip=source_ip,
                count=count,
                disposition=disposition,
                dkim_result=dkim_result,
                spf_result=spf_result,
                envelope_to=envelope_to,
                envelope_from=envelope_from,
                header_from=header_from,
                dkim_domain=dkim_domain,
                dkim_selector=dkim_selector,
                dkim_auth_result=dkim_auth_result,
                spf_domain=spf_domain,
                spf_scope=spf_scope,
                spf_auth_result=spf_auth_result
            ))

        return ReportCreate(
            report_id=report_id,
            org_name=org_name,
            email=email,
            extra_contact_info=extra_contact_info,
            date_begin=date_begin,
            date_end=date_end,
            domain=domain,
            adkim=adkim,
            aspf=aspf,
            p=p,
            sp=sp,
            pct=pct,
            records=records
        )

    except Exception as e:
        raise ValueError(f"Failed to parse DMARC XML: {str(e)}")


def parse_dmarc_report(data: bytes, filename: str) -> ReportCreate:
    """
    Parse DMARC report from compressed or uncompressed data

    Args:
        data: File data (may be compressed)
        filename: Name of the file

    Returns:
        ReportCreate object with parsed data
    """
    # Decompress if necessary
    xml_data = decompress_attachment(data, filename)

    # Parse XML
    return parse_dmarc_xml(xml_data)
