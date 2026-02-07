# DMARC Dashboard — Easy Install & Project Completion Plan

**Date:** 2026-02-07
**Goal:** Make the project easy to install, easy to set up, and production-ready.

## Context

Full audit of 30+ feature areas completed. Core finding: **all features are implemented and functional**, but the first-run experience requires manual CLI steps and tribal knowledge. 5 services lack test coverage. 3 frontend pages have minor UX issues.

## Implementation Plan

### Phase 1: Setup CLI (`make setup`)

**Task 1: Create `scripts/setup.py`**

Interactive setup script that orchestrates the entire first-run experience:

- Copies `.env.example` → `.env` with auto-generated secrets (JWT, DB password, Redis password)
- Prompts for: admin email, admin password (or auto-generate), email ingestion (optional), MaxMind geolocation (optional)
- Non-interactive mode via env vars / CLI args: `ADMIN_EMAIL`, `ADMIN_PASS`, `SKIP_EMAIL=1`, `SKIP_GEO=1`
- Runs `docker compose up -d` and waits for health checks
- Runs database migrations via `alembic upgrade head`
- Creates admin user
- Writes `.setup_complete` marker file to data volume
- Prints summary with login URL and credentials

**Task 2: Add `make setup` target to Makefile**

- Wire `make setup` to call `scripts/setup.py`
- Support passthrough of env vars for non-interactive mode

**Task 3: Update README quickstart**

- Replace multi-step instructions with `make setup`
- Keep detailed manual steps as "Advanced Setup" section

### Phase 2: Browser Setup Wizard

**Task 4: Backend setup endpoints**

- `GET /api/setup/status` — returns `{configured: bool}` based on `.setup_complete` marker
- `POST /api/setup/initialize` — accepts admin creds + optional integrations config
  - Generates secrets if not already set
  - Creates admin user
  - Writes `.setup_complete` marker
  - Returns success with redirect URL
- Both endpoints return 404 when already configured
- Rate-limited (5 requests/minute)

**Task 5: Frontend setup wizard UI**

- On page load, check `/api/setup/status` before showing login
- If unconfigured, show 5-step wizard overlay:
  1. Welcome screen
  2. Security keys (auto-generated, show confirmation)
  3. Admin account creation (email + password with strength meter)
  4. Optional integrations (email ingestion, geolocation — collapsible)
  5. Complete — redirect to login
- Minimal new code — reuse existing form patterns from Settings page

### Phase 3: Missing Tests

**Task 6: `test_api_key_auth.py`** (~150 lines)
- Key generation and SHA256 hashing
- Validation (valid key, expired key, revoked key, nonexistent key)
- X-API-Key header authentication flow

**Task 7: `test_mta_sts_service.py`** (~200 lines)
- DNS TXT record lookup and parsing
- HTTPS policy file fetch and parse
- Mode detection (none/testing/enforce)
- MX validation against DNS
- Change detection and logging

**Task 8: `test_tls_rpt_service.py`** (~200 lines)
- JSON report parsing (RFC 8460)
- Gzip/zlib decompression
- Report deduplication via SHA256
- Failure aggregation
- Trend calculation

**Task 9: `test_bimi_service.py`** (~200 lines)
- DNS record parsing
- DMARC compliance checking (p=quarantine/reject required)
- SVG logo validation (format, size, forbidden elements)
- VMC certificate structure validation
- Status classification (VALID/PARTIAL/INVALID/MISSING)

**Task 10: `test_metrics.py`** (~100 lines)
- Counter increments on requests
- Histogram bucket boundaries
- Gauge values for active connections
- Label cardinality

### Phase 4: Frontend Quick Fixes

**Task 11: Threats table pagination**
- Add pagination controls matching Reports table pattern
- Default 50 rows per page

**Task 12: ML Anomalies table pagination**
- Same pagination pattern
- Default 50 rows per page

**Task 13: Hide Notifications nav item**
- Remove or conditionally hide from sidebar
- Alert system already covers notification history

## Out of Scope

- OAuth/SAML configuration wizard (defer to Settings page)
- SAML cryptographic signature verification (acceptable for MVP)
- Saved Views cloud sync
- IE11 support
- MTA-STS/TLS-RPT/BIMI UI polish (power user features)
- Notification center (add later if users request)

## Success Criteria

- `git clone` → `make setup` → answer 4 questions → working dashboard in ~60 seconds
- `docker compose up` → open browser → wizard guides setup → working dashboard
- All services have test coverage (no zero-test features)
- No dead-end pages in the navigation
