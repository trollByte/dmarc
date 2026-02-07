# DMARC Dashboard — Product Completion Plan

## Current State Assessment

**Overall Product Maturity: ~70%**

The core DMARC ingestion, parsing, storage, and visualization pipeline works. Enterprise features (auth, alerting, ML, geolocation) are mostly implemented. However, significant gaps exist in testing, security hardening, frontend polish, infrastructure operability, and several features that are skeletons or stubs.

---

## Phase 1: Critical Fixes (Security & Broken Features)

> Things that are broken or dangerous. Must be fixed before any deployment.

### 1.1 Security Hardening

- [x] **Remove hardcoded credentials from docker-compose.yml** — Updated .env.example with security section documenting all credential variables (POSTGRES_USER/PASSWORD, REDIS_PASSWORD, FLOWER_BASIC_AUTH, JWT_SECRET_KEY). docker-compose.yml already uses env var substitution.
- [x] **Require JWT_SECRET_KEY at startup** — Added startup validation in main.py lifespan: raises RuntimeError in production if JWT key is empty/insecure, warns in debug mode.
- [x] **Secure Redis** — Already configured: --requirepass in docker-compose.yml, ports removed in docker-compose.prod.yml.
- [x] **Restrict database port** — Already configured: ports removed in docker-compose.prod.yml via `ports: !reset []`.
- [x] **Secure Flower dashboard** — Already configured: --basic-auth in docker-compose.yml, ports removed in docker-compose.prod.yml.
- [x] **Fix CSP headers** — Removed unsafe-inline from script-src, moved 2 inline event handlers to app.js. Kept unsafe-inline in style-src (required by Chart.js/Leaflet). unsafe-eval was never present.
- [x] **Validate ML model deserialization** — Added model signature constant, type checking (IsolationForest, StandardScaler), required key validation, and logging to ml_analytics.py.
- [x] **Add resource limits to Docker containers** — Already configured: all services have CPU/memory limits in docker-compose.yml.

### 1.2 Broken Frontend Features

- [x] **Add missing HTML elements for record detail view** — Already present: #recordDetail, #recordsTable, #recordsTableBody, #recordsPagination, #recordsInfo, #recordDetailContent all exist in index.html inside #tab-records.
- [x] **Add missing CSS classes** — Already present: all classes (.component-error, .input-wrapper, .input-validation-icon, .valid-icon, .invalid-icon, .input-error) exist in styles.css with theme variable support.
- [x] **Fix widget visibility toggling** — Added primary charts section toggle to applyWidgetVisibility(). Now hides/shows both primary and secondary chart sections based on pinned widgets.
- [x] **Wire up unused functions** — Connected loadComparisonData(), renderStatCardSparklines(), renderPeriodComparisons() in loadDashboard() after main tasks complete.

### 1.3 Implement Password Reset Email

- [ ] **Complete password reset flow** — `password_reset_service.py:209` has `TODO: Integrate with actual email service` — currently only logs. Wire up SMTP sending using the existing notification service's email transport.

---

## Phase 2: Test Coverage (Currently ~20% Real Coverage)

> 22 of 23 route modules have zero integration tests. Most services are untested.

### 2.1 Backend Unit Tests Needed

- [ ] **AlertService** — Alert lifecycle (create/acknowledge/resolve), deduplication, cooldowns, suppression
- [ ] **ExportService** — CSV generation, PDF generation, formula injection prevention
- [ ] **AuditService** — Log creation, filtering, retention
- [ ] **GeolocationService** — IP lookup, caching, bulk operations, graceful degradation
- [ ] **MLAnalyticsService** — Training, prediction, model versioning
- [ ] **ThreatIntelService** — AbuseIPDB integration, VirusTotal integration, caching
- [ ] **DNSMonitorService** — DNS lookups, change detection, history logging
- [ ] **ScheduledReportsService** — Schedule CRUD, next-run calculation, delivery tracking
- [ ] **RetentionService** — Policy enforcement, data cleanup
- [ ] **WebhookService** — Delivery, retry logic, signature generation
- [ ] **TOTPService** — Setup, verification, backup codes
- [ ] **SAMLService** — Metadata generation, assertion parsing
- [ ] **OAuthService** — State token generation, callback handling
- [ ] **PolicyAdvisor** — Recommendation generation, domain health scoring
- [ ] **ForecastingService** — Holt-Winters predictions, confidence intervals

### 2.2 Backend Integration Tests Needed

- [ ] **Auth routes** — Login, refresh, logout, lockout, rate limiting
- [ ] **User routes** — CRUD, API key management, role enforcement
- [ ] **Alert routes** — History, acknowledge, resolve, rules CRUD, suppressions
- [ ] **Analytics routes** — Geolocation lookup, ML model management, anomaly detection
- [ ] **Export routes** — CSV/PDF generation, rate limiting enforcement
- [ ] **Dashboard routes** — Summary, charts, widget data
- [ ] **Audit routes** — Log retrieval, filtering, statistics
- [ ] **DNS monitor routes** — Domain CRUD, check triggers
- [ ] **Notification routes** — CRUD, read/unread, counts
- [ ] **TOTP routes** — 2FA setup, verification, disable
- [ ] **Retention routes** — Policy CRUD, enforcement triggers
- [ ] **Webhook routes** — Endpoint CRUD, event listing
- [ ] **Saved view routes** — CRUD, default view
- [ ] **Scheduled reports routes** — Schedule CRUD, execution triggers
- [ ] **Threat intel routes** — IP lookup, bulk check, cache management
- [ ] **SAML/OAuth routes** — SSO flow end-to-end

### 2.3 Frontend Tests Needed

- [ ] **Component-level tests** — Chart rendering, modal interactions, filter application
- [ ] **Form validation tests** — IP address, CIDR range, date range validation
- [ ] **Error state tests** — API failure handling, retry behavior, empty states
- [ ] **Accessibility tests** — Keyboard navigation, screen reader compatibility
- [ ] **Dark mode tests** — Theme toggle, all components render correctly

### 2.4 E2E Test Gaps

- [ ] **User workflow: login -> upload -> filter -> export** — Full authenticated flow
- [ ] **Alert workflow** — Trigger alert -> view -> acknowledge -> resolve
- [ ] **Error scenarios** — Network failures, auth expiry, invalid data

---

## Phase 3: Feature Completion (Stubs & Partial Implementations)

> Features that exist as skeletons or are partially wired up.

### 3.1 Scheduled Reports — Report Data Generation is Stub

- [ ] **Implement `_generate_report_data()`** in `scheduled_reports_service.py` — Currently returns empty structure. Wire up actual data queries for each report type (DMARC summary, domain detail, threat, compliance, executive).
- [ ] **Add Celery task for scheduled delivery** — Service exists but no task triggers it on schedule.
- [ ] **Test email delivery** with PDF attachments.

### 3.2 VirusTotal Integration — Async Only, Not Wired

- [ ] **Integrate VirusTotal service with FastAPI routes** — `virustotal_service.py` uses async httpx but isn't connected to `threat_intel_routes.py`.
- [ ] **Add rate limiting** — VirusTotal free tier has strict limits (4 req/min).
- [ ] **Add fallback handling** when API is unavailable.

### 3.3 Account Lockout — No Self-Service Unlock

- [ ] **Add time-based automatic unlock** — Currently accounts locked permanently after 5 failed attempts with no user-facing unlock. Add a configurable lockout duration (e.g., 30 minutes).
- [ ] **Add email-based unlock link** as alternative.

### 3.4 SAML Single Logout — Stub

- [ ] **Implement actual SAML SLO** — `saml_routes.py` SLO endpoint just acknowledges but doesn't actually terminate the IdP session.

### 3.5 OAuth State Storage — In-Memory Only

- [ ] **Move OAuth state tokens to Redis** — Currently stored in-memory dict, which breaks in multi-worker deployments and loses state on restart.

### 3.6 DKIM Change Detection — Incomplete

- [ ] **Complete DKIM tracking in DNS monitor** — `dns_monitor.py` has placeholder for DKIM change detection.

### 3.7 ML — No LSTM Implementation

- [ ] **Decide: drop LSTM from docs or implement** — README mentions LSTM forecasting but only Holt-Winters and Isolation Forest are implemented. The Holt-Winters implementation is arguably more appropriate, so updating docs may be the right call.

### 3.8 Frontend Authentication

- [ ] **Add login/auth UI to frontend** — Backend has full JWT auth but frontend has zero auth integration. No login page, no token management, no logout button, no role-based UI visibility.

---

## Phase 4: Code Quality & Error Handling

> Bare excepts, silent failures, and code hygiene.

### 4.1 Fix Bare Except Handlers (9 instances)

- [ ] `email_client.py:73-74` — IMAP connection close: catch `IMAPError`
- [ ] `email_client.py:168-169` — Date parsing: catch `ValueError`
- [ ] `ingest/email_client.py:49-50` — IMAP logout: catch `IMAPError`
- [ ] `geolocation.py:66-67` — MaxMind close: catch `Exception` with logging
- [ ] `spf_flattening.py:339-340` — DNS resolution: catch `dns.resolver.NoAnswer`
- [ ] `tls_rpt_service.py:168-169` — Gzip decompression: catch `zlib.error`
- [ ] `dns_monitor.py:388-410` (3 instances) — DNS lookups: catch `dns.resolver.NXDOMAIN`, `NoAnswer`, `Timeout`
- [ ] `threat_intel.py:261-262` — Date parsing: catch `ValueError`
- [ ] `ingestion.py:198-199` — Generic ingestion: catch specific exceptions and log

### 4.2 Silent Failures

- [ ] `database.py:40-41` — Database connection check fails silently. Add logging.
- [ ] `app.js:1651-1652` — Cache update errors suppressed with "Ignore" comment. At minimum log to console.
- [ ] `app.js:2161-2162` — `loadReportsTable()` has no try-catch; network errors crash silently.

### 4.3 Frontend Error Handling

- [ ] **Add error display for failed dashboard component loads** — `Promise.allSettled()` tracks failures but doesn't show them to the user.
- [ ] **Add retry mechanisms** — Currently generic error messages with no retry options for API failures.
- [ ] **Add file-specific error details** for upload failures.

---

## Phase 5: Frontend Polish

> Responsive design gaps, dark mode issues, and UX improvements.

### 5.1 Responsive Design

- [ ] **Add tablet breakpoint** (768px-1024px) — Only one media query at 768px exists.
- [ ] **Add large screen layout** (>1400px) — Content stretches awkwardly.
- [ ] **Fix header actions wrapping** on mobile (480px viewport).

### 5.2 Dark Mode Completeness

- [ ] **Fix hardcoded colors** — Help modal titles use `#2c3e50` (light-only). Several components don't respect `data-theme="dark"`.
- [ ] **Audit all CSS for theme variable usage** — Replace any remaining hardcoded color values.

### 5.3 Accessibility

- [ ] **Add ARIA live regions** for dynamic content updates (chart refreshes, filter results).
- [ ] **Add `aria-sort` to sortable table headers** — Currently missing initial states.
- [ ] **Add `role="alert"` to notification toasts**.
- [ ] **Wrap filter bar in `<form>` element** for semantic HTML.

### 5.4 Dashboard Customization

- [ ] **Complete widget drag-to-reorder** — Currently "coming soon" (app.js:3461).
- [ ] **Implement actual widget visibility toggling** — Function exists but doesn't work.

### 5.5 Hardcoded Values to Configuration

- [ ] **API_BASE** (line 2) — Should be configurable
- [ ] **Auto-refresh interval** (line 1423, 60s) — Should be configurable
- [ ] **Max file upload size** (line 4047, 50MB) — Should match backend config
- [ ] **Default filter days** (line 11, 365 days) — Should be configurable

---

## Phase 6: Infrastructure & Operations

> Deployment pipeline, monitoring, operational tooling.

### 6.1 Deployment Pipeline

- [ ] **Implement actual deployment step in CI/CD** — `ci.yml` deploy job is a placeholder with comments but no implementation. Choose and implement: Kubernetes (kubectl/helm), Docker Swarm, or cloud-native (ECS/Cloud Run).
- [ ] **Add staging environment** workflow.
- [ ] **Add rollback procedure**.

### 6.2 Kubernetes Gaps

- [ ] **Add RBAC definitions** — Service accounts exist but no Roles/RoleBindings.
- [ ] **Add ResourceQuotas and LimitRanges** per namespace.
- [ ] **Add Pod Security Standards** (PSP replacement).
- [ ] **Deploy cert-manager** — Referenced in ingress but not installed.
- [ ] **Add sealed-secrets or external-secrets-operator** — Currently uses inline K8s secrets.

### 6.3 Monitoring Gaps

- [ ] **Deploy missing Prometheus exporters** — Config references PostgreSQL, Redis, Nginx, and Node exporters but none are deployed.
- [ ] **Create Grafana dashboards** — Provisioning is configured but no dashboard JSON files exist.
- [ ] **Configure Loki log retention**.
- [ ] **Define SLOs/SLIs** for the service.

### 6.4 Operational Tooling

- [ ] **Expand Makefile** — Add targets for: migrations, backup/restore, health checks, security scans, monitoring setup.
- [ ] **Create restore.sh script** — backup.sh exists but no restore counterpart.
- [ ] **Create database initialization script**.
- [ ] **Create secrets rotation script**.
- [ ] **Document disaster recovery procedures**.

### 6.5 Nginx Production Config

- [ ] **Add Cache-Control for index.html** — Currently no cache headers on HTML, so stale versions may be served.
- [ ] **Add CSP header to frontend Nginx** — Backend middleware adds it but the Nginx frontend config doesn't.
- [ ] **Add HSTS and Permissions-Policy** to Nginx.

---

## Phase 7: Documentation & Developer Experience

### 7.1 Documentation Gaps

- [ ] **API authentication docs** — Document how to obtain and use JWT tokens and API keys.
- [ ] **Frontend auth integration guide** — How the (future) login UI works.
- [ ] **Runbook for common operations** — Backup, restore, scale, rotate secrets.
- [ ] **Architecture Decision Records** — Document why key choices were made (Holt-Winters over LSTM, vanilla JS over React, etc.).

### 7.2 Developer Experience

- [ ] **Add pre-commit hooks** — Automate black, isort, flake8, eslint on commit.
- [ ] **Add `.env.example` validation** — Script to verify all required env vars are set.
- [ ] **Add seed data script** — Generate sample data for development/demo.

---

## Priority Summary

| Phase | Effort | Impact | Priority |
|-------|--------|--------|----------|
| **Phase 1: Critical Fixes** | 2-3 days | Prevents security incidents, fixes broken UI | **P0 — Do First** |
| **Phase 2: Test Coverage** | 2-3 weeks | Catches regressions, enables safe refactoring | **P1 — Do Next** |
| **Phase 3: Feature Completion** | 1-2 weeks | Closes the gap between docs and reality | **P1 — Do Next** |
| **Phase 4: Code Quality** | 2-3 days | Prevents silent bugs, improves debuggability | **P2 — Important** |
| **Phase 5: Frontend Polish** | 1 week | Professional UX, accessibility compliance | **P2 — Important** |
| **Phase 6: Infrastructure** | 1-2 weeks | Production readiness, operational maturity | **P2 — Important** |
| **Phase 7: Documentation** | 3-5 days | Developer onboarding, operational knowledge | **P3 — When Able** |

**Estimated total effort: 6-9 weeks** for a single developer, or 3-4 weeks with a small team working in parallel.
