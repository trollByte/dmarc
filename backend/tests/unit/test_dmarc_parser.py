"""Unit tests for DMARC parser"""
import pytest
import gzip
import zipfile
import io
from pathlib import Path
from app.parsers.dmarc_parser import (
    parse_dmarc_report,
    parse_xml,
    decompress_file,
    DmarcParseError,
    DmarcReport,
    DmarcRecord
)


@pytest.fixture
def fixtures_dir():
    """Get fixtures directory path"""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def valid_xml(fixtures_dir):
    """Load valid report XML"""
    with open(fixtures_dir / "valid_report.xml", "rb") as f:
        return f.read()


@pytest.fixture
def multiple_records_xml(fixtures_dir):
    """Load XML with multiple records"""
    with open(fixtures_dir / "multiple_records.xml", "rb") as f:
        return f.read()


@pytest.fixture
def malformed_xml(fixtures_dir):
    """Load malformed XML"""
    with open(fixtures_dir / "malformed.xml", "rb") as f:
        return f.read()


@pytest.fixture
def missing_fields_xml(fixtures_dir):
    """Load XML with missing optional fields"""
    with open(fixtures_dir / "missing_fields.xml", "rb") as f:
        return f.read()


@pytest.fixture
def multiple_auth_xml(fixtures_dir):
    """Load XML with multiple auth results"""
    with open(fixtures_dir / "multiple_auth_results.xml", "rb") as f:
        return f.read()


class TestDecompression:
    """Test file decompression"""

    def test_decompress_gzip(self, valid_xml):
        """Test gzip decompression"""
        compressed = gzip.compress(valid_xml)
        result = decompress_file(compressed, "report.xml.gz")
        assert result == valid_xml

    def test_decompress_zip(self, valid_xml):
        """Test zip decompression"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("report.xml", valid_xml)
        compressed = zip_buffer.getvalue()

        result = decompress_file(compressed, "report.zip")
        assert result == valid_xml

    def test_decompress_raw_xml(self, valid_xml):
        """Test raw XML (no decompression needed)"""
        result = decompress_file(valid_xml, "report.xml")
        assert result == valid_xml

    def test_decompress_empty_zip(self):
        """Test error handling for empty zip"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            pass  # Empty zip
        compressed = zip_buffer.getvalue()

        with pytest.raises(DmarcParseError, match="Empty zip file"):
            decompress_file(compressed, "empty.zip")

    def test_decompress_invalid_gzip(self):
        """Test error handling for invalid gzip"""
        with pytest.raises(DmarcParseError, match="Failed to decompress"):
            decompress_file(b"not gzip data", "report.xml.gz")


class TestXMLParsing:
    """Test XML parsing"""

    def test_parse_valid_report(self, valid_xml):
        """Test parsing a valid report"""
        report = parse_xml(valid_xml)

        assert isinstance(report, DmarcReport)
        assert report.metadata.org_name == "google.com"
        assert report.metadata.email == "noreply-dmarc-support@google.com"
        assert report.metadata.report_id == "12345678901234567890"
        assert report.policy_published.domain == "example.com"
        assert report.policy_published.p == "quarantine"
        assert report.policy_published.adkim == "r"
        assert report.policy_published.aspf == "r"
        assert report.policy_published.pct == 100
        assert len(report.records) == 1

        record = report.records[0]
        assert record.source_ip == "192.0.2.1"
        assert record.count == 5
        assert record.policy_evaluated.disposition == "none"
        assert record.policy_evaluated.dkim == "pass"
        assert record.policy_evaluated.spf == "pass"
        assert record.identifiers.header_from == "example.com"
        assert len(record.auth_results_dkim) == 1
        assert record.auth_results_dkim[0].domain == "example.com"
        assert record.auth_results_dkim[0].result == "pass"
        assert len(record.auth_results_spf) == 1
        assert record.auth_results_spf[0].result == "pass"

    def test_parse_multiple_records(self, multiple_records_xml):
        """Test parsing report with multiple records"""
        report = parse_xml(multiple_records_xml)

        assert len(report.records) == 3
        assert report.records[0].source_ip == "192.0.2.1"
        assert report.records[0].count == 10
        assert report.records[1].source_ip == "198.51.100.42"
        assert report.records[1].count == 3
        assert report.records[2].source_ip == "2001:db8::1"  # IPv6
        assert report.records[2].count == 1

    def test_parse_missing_fields(self, missing_fields_xml):
        """Test parsing report with missing optional fields"""
        report = parse_xml(missing_fields_xml)

        assert report.metadata.org_name == "minimal.com"
        assert report.policy_published.adkim is None
        assert report.policy_published.aspf is None
        assert report.policy_published.sp is None
        assert len(report.records) == 1

        record = report.records[0]
        assert record.policy_evaluated.dkim is None
        assert record.policy_evaluated.spf is None
        assert record.identifiers.envelope_from is None
        assert len(record.auth_results_dkim) == 0
        assert len(record.auth_results_spf) == 0

    def test_parse_multiple_auth_results(self, multiple_auth_xml):
        """Test parsing report with multiple DKIM and SPF results"""
        report = parse_xml(multiple_auth_xml)

        assert len(report.records) == 1
        record = report.records[0]

        # Should have multiple DKIM and SPF results
        assert len(record.auth_results_dkim) == 2
        assert record.auth_results_dkim[0].selector == "s1"
        assert record.auth_results_dkim[1].selector == "s2"

        assert len(record.auth_results_spf) == 2
        assert record.auth_results_spf[0].scope == "mfrom"
        assert record.auth_results_spf[1].scope == "helo"

    def test_parse_malformed_xml(self, malformed_xml):
        """Test error handling for malformed XML"""
        with pytest.raises(DmarcParseError, match="Failed to parse XML"):
            parse_xml(malformed_xml)

    def test_parse_invalid_xml(self):
        """Test error handling for completely invalid XML"""
        with pytest.raises(DmarcParseError, match="Failed to parse XML"):
            parse_xml(b"not xml at all")

    def test_parse_missing_feedback_root(self):
        """Test error handling for XML without feedback root"""
        xml = b'<?xml version="1.0"?><wrong_root></wrong_root>'
        with pytest.raises(DmarcParseError, match="missing 'feedback' root element"):
            parse_xml(xml)

    def test_parse_missing_metadata(self):
        """Test error handling for XML without metadata"""
        xml = b'<?xml version="1.0"?><feedback><policy_published><domain>test.com</domain><p>none</p></policy_published></feedback>'
        with pytest.raises(DmarcParseError, match="Missing report_metadata"):
            parse_xml(xml)

    def test_parse_missing_policy(self):
        """Test error handling for XML without policy"""
        xml = b'''<?xml version="1.0"?>
        <feedback>
          <report_metadata>
            <org_name>test</org_name>
            <report_id>123</report_id>
            <date_range><begin>1704067200</begin><end>1704153600</end></date_range>
          </report_metadata>
        </feedback>'''
        with pytest.raises(DmarcParseError, match="Missing policy_published"):
            parse_xml(xml)


class TestFullParsing:
    """Test full parsing pipeline"""

    def test_parse_dmarc_report_xml(self, valid_xml):
        """Test full parsing of raw XML"""
        report = parse_dmarc_report(valid_xml, "report.xml")
        assert isinstance(report, DmarcReport)
        assert report.metadata.org_name == "google.com"

    def test_parse_dmarc_report_gzip(self, valid_xml):
        """Test full parsing of gzipped report"""
        compressed = gzip.compress(valid_xml)
        report = parse_dmarc_report(compressed, "report.xml.gz")
        assert isinstance(report, DmarcReport)
        assert report.metadata.org_name == "google.com"

    def test_parse_dmarc_report_zip(self, valid_xml):
        """Test full parsing of zipped report"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("report.xml", valid_xml)
        compressed = zip_buffer.getvalue()

        report = parse_dmarc_report(compressed, "report.zip")
        assert isinstance(report, DmarcReport)
        assert report.metadata.org_name == "google.com"

    def test_date_conversion(self, valid_xml):
        """Test that Unix timestamps are converted to datetime"""
        report = parse_dmarc_report(valid_xml, "report.xml")

        # Timestamps in fixture are: begin=1704067200, end=1704153600
        assert report.metadata.date_begin.year == 2024
        assert report.metadata.date_end.year == 2024
