# Testing Documentation

## Test Coverage Summary

This project includes comprehensive test coverage for all critical components:

### Unit Tests (8 tests)

Located in `backend/tests/unit/test_parser.py`

**Test Class: TestDecompressAttachment (5 tests)**
1. `test_decompress_gzip` - Verifies gzip decompression works correctly
2. `test_decompress_zip` - Verifies zip decompression works correctly
3. `test_decompress_uncompressed` - Handles uncompressed XML files
4. `test_decompress_invalid_gzip` - Handles invalid gzip data gracefully
5. `test_decompress_empty_zip` - Handles empty zip files with proper error

**Test Class: TestParseDmarcXML (6 tests)**
6. `test_parse_valid_xml` - Parses valid DMARC XML correctly
7. `test_parse_malformed_xml` - Handles malformed XML with proper error
8. `test_parse_xml_missing_required_fields` - Validates required fields
9. `test_parse_xml_single_record` - Handles single record (not in list)
10. `test_parse_xml_multiple_dkim_spf` - Handles multiple auth results
11. `test_parse_xml_date_conversion` - Converts Unix timestamps correctly

**Test Class: TestParseDmarcReport (2 tests)**
12. `test_parse_compressed_report` - End-to-end parsing of gzipped report
13. `test_parse_uncompressed_report` - End-to-end parsing of plain XML

### Integration Tests (7 tests)

Located in `backend/tests/integration/test_ingest.py`

**Test Class: TestIngestIntegration (7 tests)**
1. `test_ingest_single_report` - Ingests a single DMARC report successfully
2. `test_ingest_idempotency` - **Ensures running ingest twice doesn't create duplicates**
3. `test_ingest_multiple_reports` - Ingests multiple reports from multiple emails
4. `test_ingest_skip_invalid_attachment` - Skips invalid attachments gracefully
5. `test_ingest_email_without_attachments` - Handles emails without attachments
6. `test_ingest_duplicate_report_different_email` - Prevents duplicate reports by report_id
7. `test_ingest_idempotency` - **Second idempotency test verifying no data duplication**

## Running Tests

### Run All Tests
```bash
docker compose exec backend pytest
```

### Run with Verbose Output
```bash
docker compose exec backend pytest -v
```

### Run with Coverage Report
```bash
docker compose exec backend pytest --cov=app --cov-report=html
```

### Run Only Unit Tests
```bash
docker compose exec backend pytest tests/unit/
```

### Run Only Integration Tests
```bash
docker compose exec backend pytest tests/integration/
```

### Run Specific Test File
```bash
docker compose exec backend pytest tests/unit/test_parser.py
```

### Run Specific Test
```bash
docker compose exec backend pytest tests/unit/test_parser.py::TestParseDmarcXML::test_parse_valid_xml
```

## Test Requirements Met

✅ **Unit Tests**: 13 tests (Required: 5+) - Testing parser and decompression
✅ **Integration Tests**: 7 tests (Required: 2+) - Testing end-to-end ingest pipeline
✅ **Idempotency**: Multiple tests verify duplicate prevention

## Test Data

Sample DMARC reports are located in `backend/sample_reports/`:
- `sample_report.xml` - Valid DMARC aggregate report
- `malformed_report.xml` - Invalid XML for error handling tests

## Continuous Integration

To run tests in CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    docker compose up -d
    docker compose exec -T backend pytest --cov=app --cov-report=xml
    docker compose down
```

## Code Quality

All tests follow best practices:
- Clear, descriptive test names
- Isolated test cases with fixtures
- Proper setup and teardown
- Comprehensive edge case coverage
- Mock external dependencies (email, network)
