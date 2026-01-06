import pytest
import gzip
import zipfile
import io
from app.ingest.parser import (
    decompress_attachment,
    parse_dmarc_xml,
    parse_dmarc_report
)


class TestDecompressAttachment:
    """Test decompression of various file formats"""

    def test_decompress_gzip(self, sample_xml):
        """Test decompressing gzip files"""
        # Compress the sample XML
        compressed = gzip.compress(sample_xml)

        # Decompress using our function
        decompressed = decompress_attachment(compressed, "report.xml.gz")

        assert decompressed == sample_xml

    def test_decompress_zip(self, sample_xml):
        """Test decompressing zip files"""
        # Create a zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("report.xml", sample_xml)
        compressed = zip_buffer.getvalue()

        # Decompress using our function
        decompressed = decompress_attachment(compressed, "report.zip")

        assert decompressed == sample_xml

    def test_decompress_uncompressed(self, sample_xml):
        """Test handling of uncompressed XML files"""
        # Should return the data as-is
        result = decompress_attachment(sample_xml, "report.xml")

        assert result == sample_xml

    def test_decompress_invalid_gzip(self):
        """Test handling of invalid gzip data"""
        invalid_data = b"This is not gzipped data"

        with pytest.raises(ValueError, match="Failed to decompress"):
            decompress_attachment(invalid_data, "report.xml.gz")

    def test_decompress_empty_zip(self):
        """Test handling of empty zip files"""
        # Create an empty zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            pass  # Don't add any files
        empty_zip = zip_buffer.getvalue()

        with pytest.raises(ValueError, match="Empty zip file"):
            decompress_attachment(empty_zip, "report.zip")


class TestParseDmarcXML:
    """Test parsing of DMARC XML data"""

    def test_parse_valid_xml(self, sample_xml):
        """Test parsing valid DMARC XML"""
        report = parse_dmarc_xml(sample_xml)

        # Check report metadata
        assert report.report_id == "12345678901234567890"
        assert report.org_name == "Google Inc."
        assert report.email == "noreply-dmarc-support@google.com"
        assert report.domain == "example.com"

        # Check policy
        assert report.p == "quarantine"
        assert report.adkim == "r"
        assert report.aspf == "r"
        assert report.pct == 100

        # Check records
        assert len(report.records) == 2

        # Check first record
        assert report.records[0].source_ip == "192.0.2.1"
        assert report.records[0].count == 5
        assert report.records[0].dkim_result == "pass"
        assert report.records[0].spf_result == "pass"
        assert report.records[0].disposition == "none"

        # Check second record
        assert report.records[1].source_ip == "203.0.113.5"
        assert report.records[1].count == 2
        assert report.records[1].dkim_result == "fail"
        assert report.records[1].spf_result == "fail"
        assert report.records[1].disposition == "quarantine"

    def test_parse_malformed_xml(self, malformed_xml):
        """Test handling of malformed XML"""
        with pytest.raises(ValueError, match="Invalid DMARC XML"):
            parse_dmarc_xml(malformed_xml)

    def test_parse_xml_missing_required_fields(self):
        """Test handling of XML with missing required fields"""
        xml_missing_report_id = b"""<?xml version="1.0"?>
        <feedback>
            <report_metadata>
                <org_name>Test Org</org_name>
                <date_range>
                    <begin>1609459200</begin>
                    <end>1609545600</end>
                </date_range>
            </report_metadata>
            <policy_published>
                <domain>example.com</domain>
            </policy_published>
        </feedback>
        """

        with pytest.raises(ValueError, match="Missing required field"):
            parse_dmarc_xml(xml_missing_report_id)

    def test_parse_xml_single_record(self):
        """Test parsing XML with a single record (not in a list)"""
        xml_single_record = b"""<?xml version="1.0"?>
        <feedback>
            <report_metadata>
                <org_name>Test Org</org_name>
                <report_id>test-123</report_id>
                <date_range>
                    <begin>1609459200</begin>
                    <end>1609545600</end>
                </date_range>
            </report_metadata>
            <policy_published>
                <domain>example.com</domain>
                <p>none</p>
            </policy_published>
            <record>
                <row>
                    <source_ip>192.0.2.1</source_ip>
                    <count>10</count>
                    <policy_evaluated>
                        <disposition>none</disposition>
                        <dkim>pass</dkim>
                        <spf>pass</spf>
                    </policy_evaluated>
                </row>
                <identifiers>
                    <header_from>example.com</header_from>
                </identifiers>
                <auth_results>
                    <dkim>
                        <domain>example.com</domain>
                        <result>pass</result>
                    </dkim>
                    <spf>
                        <domain>example.com</domain>
                        <result>pass</result>
                    </spf>
                </auth_results>
            </record>
        </feedback>
        """

        report = parse_dmarc_xml(xml_single_record)
        assert len(report.records) == 1
        assert report.records[0].source_ip == "192.0.2.1"
        assert report.records[0].count == 10

    def test_parse_xml_multiple_dkim_spf(self):
        """Test parsing XML with multiple DKIM/SPF auth results (takes first)"""
        xml_multiple_auth = b"""<?xml version="1.0"?>
        <feedback>
            <report_metadata>
                <org_name>Test Org</org_name>
                <report_id>test-456</report_id>
                <date_range>
                    <begin>1609459200</begin>
                    <end>1609545600</end>
                </date_range>
            </report_metadata>
            <policy_published>
                <domain>example.com</domain>
                <p>reject</p>
            </policy_published>
            <record>
                <row>
                    <source_ip>192.0.2.100</source_ip>
                    <count>3</count>
                    <policy_evaluated>
                        <disposition>reject</disposition>
                        <dkim>fail</dkim>
                        <spf>pass</spf>
                    </policy_evaluated>
                </row>
                <identifiers>
                    <header_from>example.com</header_from>
                </identifiers>
                <auth_results>
                    <dkim>
                        <domain>first.com</domain>
                        <selector>s1</selector>
                        <result>fail</result>
                    </dkim>
                    <dkim>
                        <domain>second.com</domain>
                        <selector>s2</selector>
                        <result>pass</result>
                    </dkim>
                    <spf>
                        <domain>example.com</domain>
                        <result>pass</result>
                    </spf>
                </auth_results>
            </record>
        </feedback>
        """

        report = parse_dmarc_xml(xml_multiple_auth)
        # Should take the first DKIM result
        assert report.records[0].dkim_domain == "first.com"
        assert report.records[0].dkim_selector == "s1"
        assert report.records[0].dkim_auth_result == "fail"

    def test_parse_xml_date_conversion(self, sample_xml):
        """Test that Unix timestamps are correctly converted to datetime"""
        report = parse_dmarc_xml(sample_xml)

        # Timestamps in sample: begin=1609459200, end=1609545600
        assert report.date_begin.year == 2021
        assert report.date_begin.month == 1
        assert report.date_end.year == 2021
        assert report.date_end.month == 1


class TestParseDmarcReport:
    """Test end-to-end DMARC report parsing"""

    def test_parse_compressed_report(self, sample_xml):
        """Test parsing gzip compressed DMARC report"""
        compressed = gzip.compress(sample_xml)
        report = parse_dmarc_report(compressed, "report.xml.gz")

        assert report.report_id == "12345678901234567890"
        assert report.org_name == "Google Inc."
        assert len(report.records) == 2

    def test_parse_uncompressed_report(self, sample_xml):
        """Test parsing uncompressed DMARC report"""
        report = parse_dmarc_report(sample_xml, "report.xml")

        assert report.report_id == "12345678901234567890"
        assert report.org_name == "Google Inc."
        assert len(report.records) == 2
