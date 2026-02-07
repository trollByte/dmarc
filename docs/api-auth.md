# API Authentication Guide

This guide covers all authentication methods for the DMARC Dashboard API.

## Authentication Methods

The DMARC Dashboard supports two authentication methods:

1. **JWT Tokens** - For user login sessions (recommended for web UI)
2. **API Keys** - For programmatic access (recommended for integrations)

## JWT Token Authentication

### 1. Obtaining JWT Tokens

**Endpoint:** `POST /api/auth/login`

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Fields:**
- `access_token`: Short-lived token (15 minutes) for API requests
- `refresh_token`: Long-lived token (7 days) for obtaining new access tokens
- `token_type`: Always "bearer"
- `expires_in`: Access token lifetime in seconds (900 = 15 minutes)

### 2. Using Tokens in Requests

Include the access token in the `Authorization` header with "Bearer" prefix:

```bash
curl -X GET http://localhost:8000/api/reports \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**JavaScript Example:**
```javascript
const response = await fetch('/api/reports', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
```

**Python Example:**
```python
import requests

headers = {
    'Authorization': f'Bearer {access_token}'
}
response = requests.get('http://localhost:8000/api/reports', headers=headers)
```

### 3. Token Refresh Flow

When the access token expires (after 15 minutes), use the refresh token to obtain a new one:

**Endpoint:** `POST /api/auth/refresh`

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Auto-Refresh Pattern (JavaScript):**
```javascript
async function fetchWithAutoRefresh(url, options = {}) {
  let response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`
    }
  });

  // If 401, try refreshing token
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      // Retry with new token
      response = await fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${accessToken}`
        }
      });
    }
  }

  return response;
}
```

### 4. Two-Factor Authentication (2FA)

If the user has 2FA enabled, login requires an additional TOTP code:

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password",
    "totp_code": "123456"
  }'
```

**Or with backup code:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password",
    "backup_code": "abcd-efgh-ijkl"
  }'
```

**Error Response (2FA required):**
```json
{
  "detail": "Two-factor authentication required"
}
```

Response includes header: `X-2FA-Required: true`

### 5. Logout

**Single Session Logout:**
```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer ${access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

**Logout All Sessions:**
```bash
curl -X POST http://localhost:8000/api/auth/logout/all \
  -H "Authorization: Bearer ${access_token}"
```

### 6. Get Current User Info

```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer ${access_token}"
```

**Response:**
```json
{
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin",
    "is_active": true,
    "totp_enabled": false,
    "created_at": "2026-01-01T00:00:00Z",
    "last_login": "2026-02-06T12:00:00Z"
  }
}
```

## API Key Authentication

API keys provide long-lived authentication for scripts and integrations without requiring login.

### 1. Creating an API Key

API keys can only be created by authenticated users (or admins on behalf of users):

**Endpoint:** `POST /api/users/api-keys`

**Request:**
```bash
curl -X POST http://localhost:8000/api/users/api-keys \
  -H "Authorization: Bearer ${access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "key_name": "Integration Script",
    "expires_at": "2027-01-01T00:00:00Z"
  }'
```

**Response:**
```json
{
  "api_key": "dmarc_live_abc123def456...",
  "key_name": "Integration Script",
  "key_prefix": "dmarc_liv",
  "expires_at": "2027-01-01T00:00:00Z",
  "created_at": "2026-02-06T12:00:00Z"
}
```

**Important:** The full `api_key` is only shown once. Store it securely.

### 2. Using API Keys

Include the API key in the `X-API-Key` header:

```bash
curl -X GET http://localhost:8000/api/reports \
  -H "X-API-Key: dmarc_live_abc123def456..."
```

**Python Example:**
```python
import requests

headers = {
    'X-API-Key': 'dmarc_live_abc123def456...'
}
response = requests.get('http://localhost:8000/api/reports', headers=headers)
```

### 3. Listing API Keys

```bash
curl -X GET http://localhost:8000/api/users/api-keys \
  -H "Authorization: Bearer ${access_token}"
```

**Response:**
```json
{
  "keys": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "key_name": "Integration Script",
      "key_prefix": "dmarc_liv",
      "is_active": true,
      "last_used": "2026-02-06T11:30:00Z",
      "expires_at": "2027-01-01T00:00:00Z",
      "created_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

### 4. Revoking API Keys

```bash
curl -X DELETE http://localhost:8000/api/users/api-keys/{key_id} \
  -H "Authorization: Bearer ${access_token}"
```

## Error Responses

### 401 Unauthorized

**Invalid credentials:**
```json
{
  "detail": "Incorrect username or password"
}
```

**Expired token:**
```json
{
  "detail": "Token has expired"
}
```

**Invalid API key:**
```json
{
  "detail": "Invalid API key"
}
```

### 403 Forbidden

**Account inactive:**
```json
{
  "detail": "Account is inactive"
}
```

**Account locked:**
```json
{
  "detail": "Account is locked due to too many failed login attempts. Contact administrator."
}
```

**Insufficient permissions:**
```json
{
  "detail": "Insufficient permissions"
}
```

## Security Best Practices

### For JWT Tokens

1. **Never log or expose tokens** - Tokens grant full access to user accounts
2. **Store refresh tokens securely** - Use httpOnly cookies or secure storage
3. **Implement token refresh** - Don't wait for 401s; refresh proactively before expiry
4. **Clear tokens on logout** - Remove from storage and revoke on backend
5. **Use HTTPS in production** - Never send tokens over unencrypted HTTP

### For API Keys

1. **Treat API keys like passwords** - Never commit to version control
2. **Use environment variables** - Store keys in `.env` files or secret managers
3. **Set expiration dates** - Use the shortest lifetime necessary
4. **Rotate keys regularly** - Especially if potentially exposed
5. **Limit scope** - Create separate keys for different integrations
6. **Monitor usage** - Check `last_used` timestamps for anomalies

### General

1. **Enable 2FA** - For all admin and analyst accounts
2. **Use strong passwords** - Minimum 12 characters with mixed case, numbers, symbols
3. **Monitor failed logins** - Accounts lock after 5 failed attempts
4. **Review active sessions** - Use `/auth/me` and `/auth/logout/all` if suspicious
5. **Audit API access** - Check audit logs for unusual patterns

## Rate Limiting

Authentication endpoints have strict rate limits:

- **Login:** 10 requests/minute per IP
- **Refresh:** 30 requests/minute per IP
- **Other API endpoints:** 100 requests/minute per IP

Rate limit headers:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 8
X-RateLimit-Reset: 1707224400
```

## Complete Example Scripts

### Python Script with API Key
```python
#!/usr/bin/env python3
import os
import requests

API_BASE = os.getenv('DMARC_API_BASE', 'http://localhost:8000/api')
API_KEY = os.getenv('DMARC_API_KEY')

if not API_KEY:
    raise ValueError('DMARC_API_KEY environment variable required')

headers = {'X-API-Key': API_KEY}

# Fetch reports
response = requests.get(f'{API_BASE}/reports', headers=headers, params={'days': 7})
response.raise_for_status()

reports = response.json()
print(f"Found {len(reports.get('data', []))} reports in last 7 days")
```

### Python Script with JWT Login
```python
#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timedelta

class DMARCClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None

    def login(self):
        response = requests.post(
            f'{self.base_url}/auth/login',
            json={'username': self.username, 'password': self.password}
        )
        response.raise_for_status()
        data = response.json()

        self.access_token = data['access_token']
        self.refresh_token = data['refresh_token']
        self.token_expires_at = datetime.now() + timedelta(seconds=data['expires_in'])

    def refresh_access_token(self):
        response = requests.post(
            f'{self.base_url}/auth/refresh',
            json={'refresh_token': self.refresh_token}
        )
        response.raise_for_status()
        data = response.json()

        self.access_token = data['access_token']
        self.token_expires_at = datetime.now() + timedelta(seconds=data['expires_in'])

    def get_headers(self):
        # Refresh if token expires in less than 1 minute
        if self.token_expires_at and datetime.now() >= self.token_expires_at - timedelta(minutes=1):
            self.refresh_access_token()

        return {'Authorization': f'Bearer {self.access_token}'}

    def get_reports(self, days=7):
        response = requests.get(
            f'{self.base_url}/reports',
            headers=self.get_headers(),
            params={'days': days}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = DMARCClient(
    base_url='http://localhost:8000/api',
    username=os.getenv('DMARC_USERNAME'),
    password=os.getenv('DMARC_PASSWORD')
)
client.login()
reports = client.get_reports(days=30)
print(f"Found {len(reports.get('data', []))} reports")
```

### Bash Script with API Key
```bash
#!/bin/bash
set -euo pipefail

API_BASE="${DMARC_API_BASE:-http://localhost:8000/api}"
API_KEY="${DMARC_API_KEY:?DMARC_API_KEY environment variable required}"

# Fetch reports from last 7 days
curl -sSL "${API_BASE}/reports?days=7" \
  -H "X-API-Key: ${API_KEY}" \
  | jq -r '.data[] | "\(.org_name): \(.domain) (\(.date_begin))"'
```

## See Also

- [API Documentation](API.md) - Complete API reference
- [User Guide](USER_GUIDE.md) - Web UI authentication
- [Frontend Authentication Guide](frontend-auth.md) - Implementation details
