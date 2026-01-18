# DMARC Dashboard API Documentation

The DMARC Dashboard provides a comprehensive REST API built with FastAPI. Interactive documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

## Base URL

```
http://localhost:8000
```

## Authentication

All protected endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login with username/password |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Logout (revoke current token) |
| POST | `/auth/logout/all` | Logout all sessions |
| GET | `/auth/me` | Get current user info |

## Core DMARC Endpoints

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/domains` | List all domains with reports |
| GET | `/api/reports` | Query DMARC reports with filters |
| GET | `/api/reports/{id}` | Get report details |
| GET | `/api/records` | Query DMARC records |
| GET | `/api/rollup/stats` | Get aggregated statistics |
| GET | `/api/rollup/timeline` | Get timeline statistics |
| GET | `/api/rollup/failure-trend` | Get failure rate trend |
| GET | `/api/rollup/top-organizations` | Get top sending organizations |
| GET | `/api/dashboard/trends` | Get sparkline and comparison data |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard/summary` | Dashboard summary with health score |
| GET | `/dashboard/widgets` | Widget data for dashboard |
| GET | `/dashboard/alerts` | Active alerts summary |
| GET | `/dashboard/auth-analysis` | DKIM/SPF authentication analysis |
| GET | `/dashboard/charts/authentication` | Authentication results chart data |
| GET | `/dashboard/charts/top-senders` | Top sending IP addresses |
| GET | `/dashboard/charts/disposition` | Message disposition breakdown |
| GET | `/dashboard/charts/geo` | Geographic distribution |

## User Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users` | List all users (admin only) |
| POST | `/users` | Create user (admin only) |
| GET | `/users/{id}` | Get user details |
| PATCH | `/users/{id}` | Update user |
| DELETE | `/users/{id}` | Delete user (admin only) |
| POST | `/users/{id}/lock` | Lock user account (admin only) |

## Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notifications` | Get user notifications |
| GET | `/notifications/count` | Get notification counts |
| GET | `/notifications/{id}` | Get specific notification |
| POST | `/notifications/{id}/read` | Mark notification as read |
| POST | `/notifications/read-all` | Mark all as read |
| DELETE | `/notifications/{id}` | Delete notification |
| DELETE | `/notifications/read/all` | Delete all read notifications |
| POST | `/notifications` | Create notification (admin) |
| POST | `/notifications/broadcast` | Broadcast to all users (admin) |

## Saved Views

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/saved-views` | List user's saved views |
| GET | `/saved-views/default` | Get user's default view |
| GET | `/saved-views/{id}` | Get specific saved view |
| POST | `/saved-views` | Create saved view |
| PATCH | `/saved-views/{id}` | Update saved view |
| DELETE | `/saved-views/{id}` | Delete saved view |
| POST | `/saved-views/{id}/use` | Mark view as used |
| POST | `/saved-views/{id}/set-default` | Set as default view |
| POST | `/saved-views/{id}/duplicate` | Duplicate a view |

## Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/alerts/active` | Get active alerts |
| GET | `/alerts/history` | Get alert history |
| POST | `/alerts/{id}/acknowledge` | Acknowledge alert |
| POST | `/alerts/{id}/resolve` | Resolve alert |
| GET | `/alerts/rules` | List alert rules |
| POST | `/alerts/rules` | Create alert rule |
| PATCH | `/alerts/rules/{id}` | Update alert rule |
| DELETE | `/alerts/rules/{id}` | Delete alert rule |

## Scheduled Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/scheduled-reports` | List scheduled reports |
| POST | `/scheduled-reports` | Create scheduled report |
| GET | `/scheduled-reports/{id}` | Get schedule details |
| PUT | `/scheduled-reports/{id}` | Update schedule |
| DELETE | `/scheduled-reports/{id}` | Delete schedule |
| POST | `/scheduled-reports/{id}/run` | Run immediately |
| GET | `/scheduled-reports/{id}/logs` | Get delivery logs |

## Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/export/reports/csv` | Export reports as CSV |
| GET | `/export/records/csv` | Export records as CSV |
| GET | `/export/sources/csv` | Export sources as CSV |
| GET | `/export/pdf` | Export as PDF report |

## Threat Intelligence

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/threat-intel/ip/{ip}` | Get threat data for IP |
| GET | `/threat-intel/summary` | Get threat summary |
| GET | `/threat-intel/top-threats` | Get top threat sources |

## DNS Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dns-monitor/domains` | List monitored domains |
| POST | `/dns-monitor/domains` | Add domain to monitor |
| DELETE | `/dns-monitor/domains/{id}` | Remove domain |
| GET | `/dns-monitor/domains/{id}/history` | Get DNS change history |

## DMARC Generator

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/generator/dmarc` | Generate DMARC record |
| POST | `/generator/spf` | Generate SPF record |
| GET | `/generator/validate/{domain}` | Validate domain setup |

## 2FA (TOTP)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/totp/setup` | Initialize TOTP setup |
| POST | `/totp/verify` | Verify TOTP code |
| POST | `/totp/disable` | Disable 2FA |
| GET | `/totp/backup-codes` | Get backup codes |

## Common Query Parameters

### Pagination

- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 10-100)

### Date Filtering

- `days`: Number of days of data (e.g., `days=30`)
- `start`: Start date (ISO format)
- `end`: End date (ISO format)

### Domain Filtering

- `domain`: Filter by domain name

## Response Formats

All responses are JSON. Successful responses:

```json
{
  "data": [...],
  "total": 100,
  "skip": 0,
  "limit": 10
}
```

Error responses:

```json
{
  "detail": "Error message"
}
```

## Rate Limiting

Default rate limits:
- 100 requests per minute per IP
- Some endpoints have specific limits (e.g., auth endpoints: 10/minute)

Rate limit headers are included in responses:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

## Webhooks

Configure webhooks to receive real-time notifications:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/webhooks` | List configured webhooks |
| POST | `/webhooks` | Create webhook |
| PATCH | `/webhooks/{id}` | Update webhook |
| DELETE | `/webhooks/{id}` | Delete webhook |
| POST | `/webhooks/{id}/test` | Send test event |

## Health & Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| GET | `/api/task-stats` | Celery task statistics |
