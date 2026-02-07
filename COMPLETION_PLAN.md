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

- [x] **Complete password reset flow** — Refactored `send_reset_email()` to use `NotificationService._send_email()` with `SMTPConfig`. Falls back to logging reset URL when SMTP not configured (dev mode).

---

## Phase 2: Test Coverage (Currently ~20% Real Coverage)

> 22 of 23 route modules have zero integration tests. Most services are untested.

### 2.1 Backend Unit Tests Needed

- [x] **AlertService** — Already has 18 tests in test_alerting_service.py (lifecycle, deduplication, cooldowns, suppression)
- [x] **ExportService** — Already has 10 tests in test_export_service.py (CSV, PDF, formula injection)
- [x] **AuditService** — Already has 25 tests in test_audit_service.py (creation, filtering, retention)
- [x] **GeolocationService** — Already has 11 tests in test_geolocation_service.py (IP lookup, caching, bulk, degradation)
- [x] **MLAnalyticsService** — Already has 11 tests in test_ml_analytics_service.py (training, prediction, versioning)
- [x] **ThreatIntelService** — Already has 15 tests in test_threat_intel_service.py (AbuseIPDB, caching)
- [x] **DNSMonitorService** — Already has 17 tests in test_dns_monitor_service.py (lookups, change detection, history)
- [x] **ScheduledReportsService** — 15 tests in test_scheduled_reports_service.py (CRUD, next-run, delivery tracking, report execution)
- [x] **RetentionService** — Already has 16 tests in test_retention_service.py (policy enforcement, cleanup)
- [x] **WebhookService** — Already has 14 tests in test_webhook_service.py (delivery, retry, signatures)
- [x] **TOTPService** — Already has 23 tests in test_totp_service.py (setup, verification, backup codes)
- [x] **SAMLService** — 22 tests in test_saml_service.py (provider CRUD, assertion parsing, user provisioning, SP metadata)
- [x] **OAuthService** — 25 tests in test_oauth_service.py (provider config, auth URLs, token exchange, user info, full auth flow)
- [x] **PolicyAdvisor** — 20 tests in test_policy_advisor.py (recommendations, domain health, failing senders, new sender analysis)
- [x] **ForecastingService** — Already has 21 tests in test_forecasting_service.py (Holt-Winters, confidence intervals)

### 2.2 Backend Integration Tests Needed

- [x] **Auth routes** — Already has 18 tests in test_auth_routes.py (login, refresh, logout, lockout)
- [x] **User routes** — Already has 26 tests in test_user_routes.py (CRUD, API keys, roles)
- [x] **Alert routes** — Already has 19 tests in test_alert_routes.py (history, acknowledge, resolve, rules)
- [x] **Analytics routes** — 29 tests in test_analytics_routes.py (geolocation, ML models, anomaly detection, forecasting)
- [x] **Export routes** — Already has 10 tests in test_export_routes.py (CSV/PDF generation)
- [x] **Dashboard routes** — Already has 10 tests in test_dashboard_routes.py (summary, charts, widgets)
- [x] **Audit routes** — Already has 14 tests in test_audit_routes.py (log retrieval, filtering, stats)
- [x] **DNS monitor routes** — 14 tests in test_dns_monitor_routes.py (domain CRUD, check triggers, history)
- [x] **Notification routes** — Already has 12 tests in test_notification_routes.py (CRUD, read/unread, counts)
- [x] **TOTP routes** — 18 tests in test_totp_routes.py (setup, verification, disable, backup codes)
- [x] **Retention routes** — Already has 17 tests in test_retention_routes.py (policy CRUD, enforcement)
- [x] **Webhook routes** — Already has 15 tests in test_webhook_routes.py (endpoint CRUD, events)
- [x] **Saved view routes** — Already has 16 tests in test_saved_view_routes.py (CRUD, default view)
- [x] **Scheduled reports routes** — 16 tests in test_scheduled_reports_routes.py (CRUD, execution triggers)
- [x] **Threat intel routes** — 20 tests in test_threat_intel_routes.py (IP lookup, bulk check, cache management)
- [x] **SAML/OAuth routes** — 71 tests in test_sso_routes.py (SAML SP metadata, login, ACS, SLO, OAuth authorize, callback)

### 2.3 Frontend Tests Needed

- [x] **Component-level tests** — Already has 17 chart tests, 28 DOM/modal tests, 51 filter tests (156 total)
- [x] **Form validation tests** — Already has IP address, CIDR range, date range validation in filters.test.js
- [x] **Error state tests** — Already has 20 tests in error-handling.test.js (retry, empty states, loading)
- [x] **Accessibility tests** — Already has keyboard navigation, focus trap, aria-live tests in dom.test.js
- [x] **Dark mode tests** — Already has theme toggle, light/dark color variant tests in charts.test.js/dom.test.js

### 2.4 E2E Test Gaps

- [x] **User workflow: login -> upload -> filter -> export** — workflow.spec.js with full authenticated flow
- [x] **Alert workflow** — alerts.spec.js with trigger, view, acknowledge, resolve
- [x] **Error scenarios** — errors.spec.js with network failures, auth expiry, invalid data

---

## Phase 3: Feature Completion (Stubs & Partial Implementations)

> Features that exist as skeletons or are partially wired up.

### 3.1 Scheduled Reports — Report Data Generation is Stub

- [x] **Implement `_generate_report_data()`** in `scheduled_reports_service.py` — Already fully implemented with DB queries for report stats, pass/fail counts, and top failing domains.
- [x] **Add Celery task for scheduled delivery** — Created `tasks/scheduled_reports.py` with `process_scheduled_reports_task`, runs every 15min via Celery Beat.
- [x] **Test email delivery** with PDF attachments — Task calls `run_schedule()` which generates PDF via ExportService and sends via SMTP.

### 3.2 VirusTotal Integration — Async Only, Not Wired

- [x] **Integrate VirusTotal service with FastAPI routes** — Already imported and used in threat_intel_routes.py check endpoint, supplements AbuseIPDB data.
- [x] **Add rate limiting** — VirusTotal service has built-in rate limiting with configurable delay.
- [x] **Add fallback handling** — Combined source approach: returns AbuseIPDB data even if VT fails.

### 3.3 Account Lockout — No Self-Service Unlock

- [x] **Add time-based automatic unlock** — Already implemented in auth_service.py: auto-unlocks after `account_lockout_duration_minutes` (default 30min) using `updated_at` as lock timestamp.
- [x] **Add email-based unlock link** — New `AccountUnlockService` with `POST /auth/unlock-request` and `POST /auth/unlock-confirm` endpoints, following password reset pattern.

### 3.4 SAML Single Logout — Stub

- [x] **Implement actual SAML SLO** — SLO endpoint now decodes SAMLRequest, extracts NameID, revokes user tokens via AuthService, returns proper LogoutResponse XML.

### 3.5 OAuth State Storage — In-Memory Only

- [x] **Move OAuth state tokens to Redis** — Now uses Redis with 10-min TTL and one-time validation. Falls back to in-memory if Redis unavailable.

### 3.6 DKIM Change Detection — Incomplete

- [x] **Complete DKIM tracking in DNS monitor** — Already fully implemented: `_check_dkim()` monitors multiple selectors (google, default, selector1, selector2), computes hashes, detects changes.

### 3.7 ML — No LSTM Implementation

- [x] **Decide: drop LSTM from docs or implement** — README does not mention LSTM. Documentation already accurately describes Holt-Winters and Isolation Forest. No action needed.

### 3.8 Frontend Authentication

- [x] **Add login/auth UI to frontend** — Already fully implemented: login overlay with form, JWT token management, auto-refresh on 401, logout button, user menu, role-based admin visibility.

---

## Phase 4: Code Quality & Error Handling

> Bare excepts, silent failures, and code hygiene.

### 4.1 Fix Bare Except Handlers (9 instances)

- [x] `email_client.py:73-74` — IMAP connection close: now catches `Exception` with logging
- [x] `email_client.py:168-169` — Date parsing: now catches `(ValueError, TypeError)`
- [x] `ingest/email_client.py:49-50` — IMAP logout: now catches `Exception` with debug logging
- [x] `geolocation.py:66-67` — MaxMind close: now catches `Exception` with debug logging
- [x] `spf_flattening.py:339-340` — DNS resolution: now catches specific DNS exceptions
- [x] `tls_rpt_service.py:168-169` — Gzip decompression: now catches `(zlib.error, OSError)`
- [x] `dns_monitor.py:388-410` (3 instances) — DNS lookups: now catches specific DNS exceptions
- [x] `threat_intel.py:261-262` — Date parsing: now catches `(ValueError, TypeError)`
- [x] `ingestion.py:198-199` — Already uses `except Exception` with logging (no bare except)

### 4.2 Silent Failures

- [x] `database.py:40-41` — Changed to `logger.error()` for database connection check failures
- [x] `app.js:1651-1652` — Now logs `console.warn('Cache update failed:', e)` instead of suppressing
- [x] `app.js:2161-2162` — Added `showNotification('Failed to load reports', 'error')` in catch block

### 4.3 Frontend Error Handling

- [x] **Add error display for failed dashboard component loads** — showNotification now shows which components failed with actionable retry button.
- [x] **Add retry mechanisms** — Enhanced showNotification() with optional retryCallback parameter; retry button on dashboard load failures.
- [x] **Add file-specific error details** for upload failures — Enhanced error extraction from server responses with detailed backend error messages.

---

## Phase 5: Frontend Polish

> Responsive design gaps, dark mode issues, and UX improvements.

### 5.1 Responsive Design

- [x] **Add tablet breakpoint** (768px-1024px) — 2-column grid for stat cards and charts with optimized padding.
- [x] **Add large screen layout** (>1400px) — 4-column stat card grid, 2-column chart grid, max-width 1600px.
- [x] **Fix header actions wrapping** on mobile (480px viewport) — Single column grid, full-width buttons, smaller font.

### 5.2 Dark Mode Completeness

- [x] **Fix hardcoded colors** — Replaced 40+ hardcoded hex values with CSS custom properties. Added 7 sidebar-specific theme variables.
- [x] **Audit all CSS for theme variable usage** — Badges, buttons, borders, alerts, sidebar, tables all now use theme variables.

### 5.3 Accessibility

- [x] **Add ARIA live regions** — Added `aria-live="polite"` to stats, charts, and table sections; `aria-live="assertive"` to notifications
- [x] **Add `aria-sort` to sortable table headers** — Dynamic `aria-sort="none"` on init, updated to ascending/descending on sort.
- [x] **Add `role="alert"` to notification toasts** — Added to both HTML and dynamic JS `showNotification()` function
- [x] **Wrap filter bar in `<form>` element** — Already implemented with `role="search"` and form submission prevention.

### 5.4 Dashboard Customization

- [x] **Complete widget drag-to-reorder** — HTML5 drag-and-drop with localStorage persistence, visual feedback during drag.
- [x] **Implement actual widget visibility toggling** — Enhanced applyWidgetVisibility() to properly show/hide individual chart containers based on preferences.

### 5.5 Hardcoded Values to Configuration

- [x] **API_BASE** — Now configurable via `window.DMARC_CONFIG.apiBase`
- [x] **Auto-refresh interval** — Now configurable via `window.DMARC_CONFIG.autoRefreshInterval`
- [x] **Max file upload size** — Now configurable via `window.DMARC_CONFIG.maxUploadSize`
- [x] **Default filter days** — Now configurable via `window.DMARC_CONFIG.defaultFilterDays`

---

## Phase 6: Infrastructure & Operations

> Deployment pipeline, monitoring, operational tooling.

### 6.1 Deployment Pipeline

- [x] **Implement actual deployment step in CI/CD** — Docker Compose SSH deployment in ci.yml with health checks and image tagging.
- [x] **Add staging environment** workflow — Deploys to staging on PR merge or manual trigger with separate config.
- [x] **Add rollback procedure** — Manual dispatch workflow with rollback tag input, backup validation, and verification.

### 6.2 Kubernetes Gaps

- [x] **Add RBAC definitions** — k8s/base/rbac.yaml with ServiceAccounts, Roles, RoleBindings for backend and Celery.
- [x] **Add ResourceQuotas and LimitRanges** — k8s/base/resource-quotas.yaml with namespace CPU/memory/object limits.
- [x] **Add Pod Security Standards** — k8s/base/pod-security.yaml with restricted PSS, SecurityContext, NetworkPolicy.
- [x] **Deploy cert-manager** — k8s/base/cert-manager.yaml with Let's Encrypt ClusterIssuers and Certificate resources.
- [x] **Add sealed-secrets or external-secrets-operator** — k8s/base/external-secrets.yaml with AWS/Vault/GCP SecretStores.

### 6.3 Monitoring Gaps

- [x] **Deploy missing Prometheus exporters** — Docker Compose and K8s configs for postgres, redis, nginx, node exporters with custom DMARC queries.
- [x] **Create Grafana dashboards** — System health and infrastructure JSON dashboards with API, DB, cache, and host metrics.
- [x] **Configure Loki log retention** — Already configured with 30-day retention in monitoring/loki/loki-config.yml.
- [x] **Define SLOs/SLIs** — docs/slos.md with 6 SLOs: availability, latency, error rate, data freshness, DB perf, task success.

### 6.4 Operational Tooling

- [x] **Expand Makefile** — Added targets: migrate, backup, restore, health, lint, seed, init-db, rotate-secrets with categorized help.
- [x] **Create restore.sh script** — Already existed with --latest, --list, --verify flags and format support.
- [x] **Create database initialization script** — scripts/init-db.sh with migrations, --create-admin, service readiness check.
- [x] **Create secrets rotation script** — scripts/rotate-secrets.sh with --dry-run, --all, automatic backup and service restart.
- [x] **Document disaster recovery procedures** — docs/DISASTER_RECOVERY.md with backup verification, failover, data recovery, checklists.

### 6.5 Nginx Production Config

- [x] **Add Cache-Control for index.html** — HTML: no-cache, must-revalidate. Static assets: 1-year immutable cache.
- [x] **Add CSP header to frontend Nginx** — Matching backend CSP with self, CDN sources, Chart.js exceptions.
- [x] **Add HSTS and Permissions-Policy** to Nginx — HSTS with includeSubDomains, Permissions-Policy disabling unused features.

---

## Phase 7: Documentation & Developer Experience

### 7.1 Documentation Gaps

- [x] **API authentication docs** — docs/api-auth.md with JWT flow, API keys, 2FA, curl examples.
- [x] **Frontend auth integration guide** — docs/frontend-auth.md with login flow, token management, role-based UI.
- [x] **Runbook for common operations** — docs/runbook.md with backup/restore, scaling, secret rotation, troubleshooting.
- [x] **Architecture Decision Records** — docs/adr/ with ADRs for vanilla JS, Holt-Winters, and Celery+APScheduler.

### 7.2 Developer Experience

- [x] **Add pre-commit hooks** — .pre-commit-config.yaml with black, isort, flake8, eslint, trailing whitespace, private key detection.
- [x] **Add `.env.example` validation** — scripts/check-env.sh comparing .env against .env.example with --strict mode.
- [x] **Add seed data script** — Enhanced scripts/seed_data.py with users, alert rules, and 15 sample DMARC reports.

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
