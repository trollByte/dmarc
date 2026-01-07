"""Integration tests for report processing"""
import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from app.models import IngestedReport, DmarcReport, DmarcRecord
from app.services.processing import ReportProcessor


@pytest.fixture
def sample_xml_path():
    """Get path to sample XML files"""
    return Path(__file__).parent.parent.parent / "samples"


@pytest.fixture
def temp_storage(db_session):
    """Create temporary storage directory with test files"""
    temp_dir = tempfile.mkdtemp()

    # Create a subdirectory structure
    storage_path = Path(temp_dir)
    (storage_path / "2024" / "01" / "01").mkdir(parents=True, exist_ok=True)

    yield storage_path

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def processor(db_session, temp_storage):
    """Create a ReportProcessor instance"""
    return ReportProcessor(db_session, str(temp_storage))


class TestReportProcessor:
    """Test report processing"""

    def test_process_single_pending_report(self, processor, db_session, temp_storage, sample_xml_path):
        """Test processing a single pending report"""
        # Copy sample XML to temp storage
        sample_file = sample_xml_path / "google-report.xml"
        storage_rel_path = "2024/01/01/test-report.xml"
        storage_full_path = temp_storage / storage_rel_path

        with open(sample_file, 'rb') as f:
            content = f.read()

        with open(storage_full_path, 'wb') as f:
            f.write(content)

        # Create an ingested report record
        ingested = IngestedReport(
            message_id="<test@example.com>",
            received_at=datetime(2024, 1, 1, 12, 0, 0),
            filename="test-report.xml",
            content_hash="abc123",
            file_size=len(content),
            storage_path=storage_rel_path,
            status='pending'
        )
        db_session.add(ingested)
        db_session.commit()

        # Process pending reports
        processed, failed = processor.process_pending_reports()

        assert processed == 1
        assert failed == 0

        # Check ingested report was updated
        db_session.refresh(ingested)
        assert ingested.status == 'completed'
        assert ingested.parse_error is None

        # Check DMARC report was created
        dmarc_report = db_session.query(DmarcReport).first()
        assert dmarc_report is not None
        assert dmarc_report.report_id == "15719544134689869824"
        assert dmarc_report.org_name == "google.com"
        assert dmarc_report.domain == "example.com"
        assert dmarc_report.p == "quarantine"
        assert dmarc_report.ingested_report_id == ingested.id

        # Check DMARC records were created
        records = db_session.query(DmarcRecord).filter(
            DmarcRecord.report_id == dmarc_report.id
        ).all()
        assert len(records) == 2

        # Check first record (pass)
        record1 = next(r for r in records if r.source_ip == "209.85.220.41")
        assert record1.count == 125
        assert record1.dkim == "pass"
        assert record1.spf == "pass"
        assert record1.disposition == "none"
        assert record1.dkim_result == "pass"
        assert record1.spf_result == "pass"

        # Check second record (fail)
        record2 = next(r for r in records if r.source_ip == "192.0.2.1")
        assert record2.count == 3
        assert record2.dkim == "fail"
        assert record2.spf == "fail"
        assert record2.disposition == "quarantine"

    def test_process_multiple_pending_reports(self, processor, db_session, temp_storage, sample_xml_path):
        """Test processing multiple pending reports"""
        # Create two ingested reports
        for i, filename in enumerate(["google-report.xml", "yahoo-report.xml"]):
            sample_file = sample_xml_path / filename
            storage_rel_path = f"2024/01/01/report-{i}.xml"
            storage_full_path = temp_storage / storage_rel_path

            with open(sample_file, 'rb') as f:
                content = f.read()

            with open(storage_full_path, 'wb') as f:
                f.write(content)

            ingested = IngestedReport(
                message_id=f"<test{i}@example.com>",
                received_at=datetime(2024, 1, 1, 12, 0, 0),
                filename=filename,
                content_hash=f"hash{i}",
                file_size=len(content),
                storage_path=storage_rel_path,
                status='pending'
            )
            db_session.add(ingested)

        db_session.commit()

        # Process all pending reports
        processed, failed = processor.process_pending_reports()

        assert processed == 2
        assert failed == 0

        # Check both DMARC reports were created
        dmarc_reports = db_session.query(DmarcReport).all()
        assert len(dmarc_reports) == 2

        # Check total records
        total_records = db_session.query(DmarcRecord).count()
        assert total_records == 5  # 2 from google + 3 from yahoo

    def test_process_duplicate_report_id(self, processor, db_session, temp_storage, sample_xml_path):
        """Test that duplicate report_ids are skipped"""
        # Create first ingested report
        sample_file = sample_xml_path / "google-report.xml"
        storage_rel_path = "2024/01/01/report-1.xml"
        storage_full_path = temp_storage / storage_rel_path

        with open(sample_file, 'rb') as f:
            content = f.read()

        with open(storage_full_path, 'wb') as f:
            f.write(content)

        ingested1 = IngestedReport(
            message_id="<test1@example.com>",
            received_at=datetime(2024, 1, 1, 12, 0, 0),
            filename="report-1.xml",
            content_hash="hash1",
            file_size=len(content),
            storage_path=storage_rel_path,
            status='pending'
        )
        db_session.add(ingested1)
        db_session.commit()

        # Process first report
        processed, failed = processor.process_pending_reports()
        assert processed == 1

        # Create second ingested report with same XML (duplicate report_id)
        storage_rel_path2 = "2024/01/01/report-2.xml"
        storage_full_path2 = temp_storage / storage_rel_path2

        with open(storage_full_path2, 'wb') as f:
            f.write(content)

        ingested2 = IngestedReport(
            message_id="<test2@example.com>",
            received_at=datetime(2024, 1, 1, 13, 0, 0),
            filename="report-2.xml",
            content_hash="hash2",
            file_size=len(content),
            storage_path=storage_rel_path2,
            status='pending'
        )
        db_session.add(ingested2)
        db_session.commit()

        # Process second report
        processed, failed = processor.process_pending_reports()
        assert processed == 1  # Still marked as processed
        assert failed == 0

        # Should still only have one DMARC report
        dmarc_reports = db_session.query(DmarcReport).all()
        assert len(dmarc_reports) == 1

        # Both ingested reports should be marked completed
        db_session.refresh(ingested1)
        db_session.refresh(ingested2)
        assert ingested1.status == 'completed'
        assert ingested2.status == 'completed'

    def test_process_missing_file(self, processor, db_session, temp_storage):
        """Test handling of missing file"""
        # Create ingested report with non-existent file
        ingested = IngestedReport(
            message_id="<test@example.com>",
            received_at=datetime(2024, 1, 1, 12, 0, 0),
            filename="missing.xml",
            content_hash="hash",
            file_size=100,
            storage_path="2024/01/01/missing.xml",
            status='pending'
        )
        db_session.add(ingested)
        db_session.commit()

        # Process should fail gracefully
        processed, failed = processor.process_pending_reports()

        assert processed == 0
        assert failed == 1

        # Check ingested report was marked failed
        db_session.refresh(ingested)
        assert ingested.status == 'failed'
        assert 'not found' in ingested.parse_error.lower()

    def test_process_invalid_xml(self, processor, db_session, temp_storage):
        """Test handling of invalid XML"""
        # Create invalid XML file
        storage_rel_path = "2024/01/01/invalid.xml"
        storage_full_path = temp_storage / storage_rel_path

        with open(storage_full_path, 'wb') as f:
            f.write(b"This is not valid XML")

        ingested = IngestedReport(
            message_id="<test@example.com>",
            received_at=datetime(2024, 1, 1, 12, 0, 0),
            filename="invalid.xml",
            content_hash="hash",
            file_size=22,
            storage_path=storage_rel_path,
            status='pending'
        )
        db_session.add(ingested)
        db_session.commit()

        # Process should fail gracefully
        processed, failed = processor.process_pending_reports()

        assert processed == 0
        assert failed == 1

        # Check ingested report was marked failed
        db_session.refresh(ingested)
        assert ingested.status == 'failed'
        assert ingested.parse_error is not None

    def test_process_with_limit(self, processor, db_session, temp_storage, sample_xml_path):
        """Test processing with limit parameter"""
        # Create 5 ingested reports
        sample_file = sample_xml_path / "google-report.xml"

        for i in range(5):
            storage_rel_path = f"2024/01/01/report-{i}.xml"
            storage_full_path = temp_storage / storage_rel_path

            with open(sample_file, 'rb') as f:
                content = f.read()

            # Modify report_id to make each unique
            content = content.replace(
                b"15719544134689869824",
                f"1571954413468986982{i}".encode()
            )

            with open(storage_full_path, 'wb') as f:
                f.write(content)

            ingested = IngestedReport(
                message_id=f"<test{i}@example.com>",
                received_at=datetime(2024, 1, 1, 12, 0, 0),
                filename=f"report-{i}.xml",
                content_hash=f"hash{i}",
                file_size=len(content),
                storage_path=storage_rel_path,
                status='pending'
            )
            db_session.add(ingested)

        db_session.commit()

        # Process only 3 reports
        processed, failed = processor.process_pending_reports(limit=3)

        assert processed == 3
        assert failed == 0

        # Should still have 2 pending
        pending_count = db_session.query(IngestedReport).filter(
            IngestedReport.status == 'pending'
        ).count()
        assert pending_count == 2

    def test_reprocess_failed_reports(self, processor, db_session, temp_storage, sample_xml_path):
        """Test reprocessing failed reports"""
        # Create a valid report but mark it as failed initially
        sample_file = sample_xml_path / "google-report.xml"
        storage_rel_path = "2024/01/01/test-report.xml"
        storage_full_path = temp_storage / storage_rel_path

        with open(sample_file, 'rb') as f:
            content = f.read()

        with open(storage_full_path, 'wb') as f:
            f.write(content)

        ingested = IngestedReport(
            message_id="<test@example.com>",
            received_at=datetime(2024, 1, 1, 12, 0, 0),
            filename="test-report.xml",
            content_hash="abc123",
            file_size=len(content),
            storage_path=storage_rel_path,
            status='failed',
            parse_error='Previous error'
        )
        db_session.add(ingested)
        db_session.commit()

        # Reprocess failed reports
        processed, failed = processor.reprocess_failed_reports()

        assert processed == 1
        assert failed == 0

        # Check report is now completed
        db_session.refresh(ingested)
        assert ingested.status == 'completed'
        assert ingested.parse_error is None

        # Check DMARC report was created
        dmarc_report = db_session.query(DmarcReport).first()
        assert dmarc_report is not None
