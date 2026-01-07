# Testing Guide

This document provides comprehensive information about testing the DMARC Report Processor.

## Table of Contents

1. [Overview](#overview)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Test Coverage](#test-coverage)
5. [Writing Tests](#writing-tests)
6. [CI/CD Integration](#cicd-integration)

---

## Overview

The project uses **pytest** as the testing framework with the following features:

- **Unit tests**: Fast, isolated tests for individual components
- **Integration tests**: Tests that verify component interactions
- **Test fixtures**: Reusable test data and setup
- **Code coverage**: Minimum 70% coverage enforced
- **Continuous Integration**: Automated testing via GitHub Actions

---

## Test Structure

```
backend/tests/
├── __init__.py
├── conftest.py                    # Shared fixtures and configuration
├── fixtures/                      # Sample DMARC XML files
│   ├── valid_report.xml
│   ├── multiple_records.xml
│   ├── malformed.xml
│   ├── missing_fields.xml
│   └── multiple_auth_results.xml
├── unit/                          # Unit tests
│   ├── __init__.py
│   ├── test_dmarc_parser.py      # DMARC parser tests
│   ├── test_storage.py           # Storage service tests
│   └── test_email_client.py      # Email client tests
└── integration/                   # Integration tests
    ├── __init__.py
    ├── test_api.py               # API endpoint tests
    ├── test_ingestion.py         # Ingestion workflow tests
    └── test_processing.py        # Report processing tests
```

---

## Running Tests

### Prerequisites

Ensure dependencies are installed:

```bash
cd backend
pip install -r requirements.txt
```

### Run All Tests

```bash
# Run all tests with verbose output
pytest -v

# Run all tests with coverage report
pytest --cov=app --cov-report=term-missing
```

### Run Specific Test Categories

```bash
# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run tests by marker
pytest -m unit
pytest -m integration
```

### Run Specific Test Files

```bash
# Run parser tests
pytest tests/unit/test_dmarc_parser.py -v

# Run API tests
pytest tests/integration/test_api.py -v
```

### Run Specific Test Functions

```bash
# Run a specific test function
pytest tests/unit/test_dmarc_parser.py::TestDecompression::test_decompress_gzip -v

# Run all tests matching a pattern
pytest -k "test_upload" -v
```

### Advanced Options

```bash
# Run with detailed output and show local variables on failure
pytest -vv --showlocals

# Run and stop at first failure
pytest -x

# Run with parallel execution (requires pytest-xdist)
pytest -n auto

# Generate HTML coverage report
pytest --cov=app --cov-report=html
# Then open htmlcov/index.html in browser
```

---

## Test Coverage

### Current Coverage

The project enforces a **minimum 70% code coverage**. Tests will fail if coverage drops below this threshold.

### Coverage Reports

```bash
# Terminal report with missing lines
pytest --cov=app --cov-report=term-missing

# Generate HTML report
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Generate XML report (for CI)
pytest --cov=app --cov-report=xml
```

### Coverage Configuration

Coverage settings are in `pytest.ini`:

```ini
[coverage:run]
source = app
omit =
    */tests/*
    */migrations/*
    */__pycache__/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False
```

---

## Writing Tests

### Test Fixtures

Common fixtures are defined in `conftest.py`:

```python
@pytest.fixture
def db_session():
    """Provides a test database session"""
    # SQLite in-memory database for tests

@pytest.fixture
def temp_storage():
    """Provides temporary storage directory"""

@pytest.fixture
def sample_xml():
    """Provides sample DMARC XML content"""
```

### Unit Test Example

```python
"""tests/unit/test_example.py"""
import pytest
from app.services.example import ExampleService

class TestExampleService:
    """Test the example service"""

    def test_process_data(self):
        """Test data processing"""
        service = ExampleService()
        result = service.process("test data")
        assert result == "processed: test data"

    def test_error_handling(self):
        """Test error handling"""
        service = ExampleService()
        with pytest.raises(ValueError):
            service.process(None)
```

### Integration Test Example

```python
"""tests/integration/test_example_api.py"""
import pytest
from fastapi.testclient import TestClient

class TestExampleAPI:
    """Test example API endpoints"""

    def test_get_endpoint(self, client):
        """Test GET endpoint"""
        response = client.get("/api/example")
        assert response.status_code == 200
        assert "data" in response.json()

    def test_post_endpoint(self, client, sample_data):
        """Test POST endpoint with sample data"""
        response = client.post("/api/example", json=sample_data)
        assert response.status_code == 201
```

### Best Practices

1. **Naming**: Test files start with `test_`, test functions start with `test_`
2. **Organization**: Group related tests in classes
3. **Isolation**: Each test should be independent
4. **Clarity**: Use descriptive test names and docstrings
5. **Fixtures**: Reuse fixtures for common setup
6. **Assertions**: Use specific assertions with helpful messages
7. **Coverage**: Aim for high coverage, but prioritize meaningful tests

---

## CI/CD Integration

### GitHub Actions

Tests run automatically on:
- **Push** to `main` or `develop` branches
- **Pull requests** to `main` or `develop`
- **Manual workflow dispatch**

### Workflow Jobs

1. **Test**: Run all tests with coverage
2. **Lint**: Code quality checks (flake8, black, isort)
3. **Security**: Security scans (safety, bandit)
4. **Docker**: Build Docker images
5. **Deploy**: Manual deployment (production only)

### CI Configuration

See `.github/workflows/ci.yml` for the complete workflow.

### Local CI Simulation

You can simulate CI checks locally:

```bash
# Run tests like CI
cd backend
pytest -v --cov=app --cov-report=term-missing

# Run linting checks
flake8 app --count --select=E9,F63,F7,F82
black --check app
isort --check-only app

# Run security scans
safety check --file requirements.txt
bandit -r app
```

---

## Test Markers

Mark tests for selective execution:

```python
@pytest.mark.unit
def test_unit_example():
    """Fast unit test"""
    pass

@pytest.mark.integration
def test_integration_example():
    """Integration test with dependencies"""
    pass

@pytest.mark.slow
def test_slow_example():
    """Test that takes significant time"""
    pass

@pytest.mark.skip_ci
def test_local_only():
    """Test that runs only locally"""
    pass
```

Run tests by marker:

```bash
pytest -m unit          # Only unit tests
pytest -m "not slow"    # Exclude slow tests
```

---

## Troubleshooting

### Common Issues

**Tests fail with database errors:**
```bash
# Ensure test database is clean
rm test_*.db
```

**Import errors:**
```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Coverage too low:**
```bash
# Generate detailed coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html
# Focus on untested files/lines
```

**Slow tests:**
```bash
# Show test durations
pytest --durations=10

# Run only fast tests
pytest -m "not slow"
```

---

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [FastAPI testing guide](https://fastapi.tiangolo.com/tutorial/testing/)

---

For questions or issues, please open a GitHub issue or consult the main README.md.
