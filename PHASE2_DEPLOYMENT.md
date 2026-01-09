# Phase 2: User Authentication & RBAC Deployment Guide

## ✅ Phase 2 Complete - JWT Authentication with Role-Based Access Control

All Phase 2 components have been successfully implemented and are ready for deployment.

---

## 📦 What Was Built

### Core Authentication
- ✅ **JWT Token System** - Access tokens (15min) + Refresh tokens (7 days)
- ✅ **Password Security** - bcrypt hashing (12 rounds)
- ✅ **API Key Support** - Alternative authentication method (SHA256 hashed)
- ✅ **Role-Based Access Control (RBAC)** - Admin, Analyst, Viewer roles

### User Management
- ✅ **User CRUD** - Create, read, update, delete users (admin only)
- ✅ **Account Security** - Login attempt tracking, account lockout
- ✅ **Password Policy** - Min 12 chars, complexity requirements
- ✅ **API Key Management** - Per-user API keys with expiration

### Database Schema
- ✅ `users` - User accounts with roles
- ✅ `user_api_keys` - API keys for programmatic access
- ✅ `refresh_tokens` - JWT refresh token tracking

### API Endpoints

**Authentication:**
- ✅ `POST /auth/login` - Login with username/password
- ✅ `POST /auth/refresh` - Refresh access token
- ✅ `POST /auth/logout` - Logout (revoke refresh token)
- ✅ `POST /auth/logout/all` - Logout all sessions
- ✅ `GET /auth/me` - Get current user info

**User Management (Admin Only):**
- ✅ `POST /users` - Create new user
- ✅ `GET /users` - List all users (with pagination)
- ✅ `GET /users/{user_id}` - Get user by ID
- ✅ `PATCH /users/{user_id}` - Update user
- ✅ `DELETE /users/{user_id}` - Delete user
- ✅ `POST /users/{user_id}/unlock` - Unlock locked account

**User Self-Service:**
- ✅ `POST /users/me/change-password` - Change own password
- ✅ `POST /users/me/api-keys` - Create API key
- ✅ `GET /users/me/api-keys` - List own API keys
- ✅ `DELETE /users/me/api-keys/{key_id}` - Delete API key

---

## 🚀 Deployment Steps

### 1. Generate JWT Secret Key

**CRITICAL:** Generate a secure random key for JWT signing:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copy the output and add to `.env` file:

```bash
# Add this to .env
JWT_SECRET_KEY=<paste-generated-key-here>
```

**Security Note:** This key must be:
- At least 32 characters (64+ recommended)
- Kept secret (never commit to git)
- Different for each environment (dev, staging, prod)

### 2. Pull Latest Changes

```bash
git pull origin main
```

### 3. Install New Dependencies

```bash
docker compose exec backend pip install -r requirements.txt
```

Or rebuild containers:

```bash
docker compose build backend
```

### 4. Run Database Migration

```bash
docker compose exec backend alembic upgrade head
```

Expected output:

```
INFO  [alembic.runtime.migration] Running upgrade 004 -> 005, add user authentication
```

### 5. Restart Backend Service

```bash
docker compose restart backend
```

### 6. Create First Admin User

Run the bootstrap script interactively:

```bash
docker compose exec -it backend python scripts/create_admin_user.py
```

**Interactive prompts:**

```
==========================================================
  DMARC Dashboard - Create Admin User
==========================================================

Creating new admin user...

Username: admin
Email: admin@example.com
Password: ****************
Confirm password: ****************

Summary:
  Username: admin
  Email:    admin@example.com
  Role:     admin

Create this admin user? (yes/no): yes

==========================================================
✅ Admin user created successfully!
==========================================================

User ID:  a1b2c3d4-...
Username: admin
Email:    admin@example.com
Role:     admin
```

---

## 🔍 Testing & Verification

### Test 1: Login and Get Tokens

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your-password"
  }'
```

**Expected response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Save the access_token** - you'll need it for subsequent requests!

### Test 2: Get Current User Info

```bash
curl "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer <access_token>"
```

**Expected response:**

```json
{
  "user": {
    "id": "uuid",
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin",
    "is_active": true,
    "is_locked": false,
    "created_at": "2026-01-09T14:00:00",
    "last_login": "2026-01-09T14:05:00"
  },
  "permissions": [
    "users:create", "users:read", "users:update", "users:delete",
    "reports:create", "reports:read", "reports:update", "reports:delete",
    "alerts:read", "alerts:update", "system:manage"
  ]
}
```

### Test 3: Create Additional User

```bash
curl -X POST "http://localhost:8000/users" \
  -H "Authorization: Bearer <admin_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "analyst1",
    "email": "analyst@example.com",
    "password": "SecurePassword123!",
    "role": "analyst"
  }'
```

**Expected response:**

```json
{
  "id": "uuid",
  "username": "analyst1",
  "email": "analyst@example.com",
  "role": "analyst",
  "is_active": true,
  "is_locked": false,
  "created_at": "2026-01-09T14:10:00",
  "last_login": null
}
```

### Test 4: Create API Key

```bash
curl -X POST "http://localhost:8000/users/me/api-keys" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "key_name": "Production Server",
    "expires_days": 90
  }'
```

**Expected response:**

```json
{
  "id": "uuid",
  "key_name": "Production Server",
  "api_key": "dmarc_abc123def456...",  // ⚠️ SAVE THIS - NEVER SHOWN AGAIN
  "key_prefix": "dmarc_ab",
  "expires_at": "2026-04-09T14:00:00",
  "created_at": "2026-01-09T14:00:00"
}
```

**IMPORTANT:** Save the `api_key` immediately - it's only shown once!

### Test 5: Use API Key Authentication

```bash
curl "http://localhost:8000/auth/me" \
  -H "X-API-Key: dmarc_abc123def456..."
```

Should return the same user info as Test 2.

### Test 6: Refresh Access Token

```bash
curl -X POST "http://localhost:8000/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<refresh_token_from_login>"
  }'
```

**Expected response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",  // New access token
  "token_type": "bearer",
  "expires_in": 900
}
```

---

## 🔧 Configuration

### Password Policy (in .env)

```bash
# Password requirements (defaults shown)
PASSWORD_MIN_LENGTH=12
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_LOWERCASE=true
PASSWORD_REQUIRE_DIGIT=true
PASSWORD_REQUIRE_SPECIAL=true
```

### JWT Token Expiration

```bash
# JWT token lifetimes (defaults shown)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15   # Access token (short-lived)
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7      # Refresh token (long-lived)
```

### Account Security

```bash
# Account lockout settings (defaults shown)
MAX_FAILED_LOGIN_ATTEMPTS=5
ACCOUNT_LOCKOUT_DURATION_MINUTES=30
```

---

## 🔐 Security Features

### Authentication Methods

1. **JWT Tokens (Recommended)**
   - Short-lived access tokens (15min)
   - Long-lived refresh tokens (7 days)
   - Revocable via logout endpoints

2. **API Keys (Alternative)**
   - Per-user API keys with SHA256 hashing
   - Optional expiration dates
   - Last used tracking

### Password Security

- **bcrypt hashing** with 12 rounds
- **Complexity requirements:**
  - Minimum 12 characters
  - Uppercase + lowercase letters
  - Digits + special characters
- **Plaintext passwords never stored**

### Account Protection

- **Failed login tracking** - locks after 5 attempts
- **Account lockout** - requires admin unlock
- **Session management** - logout single or all sessions
- **Audit trail** - login times, IP addresses tracked

### Role-Based Access Control (RBAC)

**Admin:**
- Full system access
- User management (create, update, delete)
- System configuration

**Analyst:**
- Read/write reports
- Read/write alerts
- No user management

**Viewer:**
- Read-only access
- View reports and alerts
- No modifications

---

## 🔑 User Roles & Permissions

| Permission | Admin | Analyst | Viewer |
|-----------|-------|---------|--------|
| Create users | ✅ | ❌ | ❌ |
| View users | ✅ | ❌ | ❌ |
| Update users | ✅ | ❌ | ❌ |
| Delete users | ✅ | ❌ | ❌ |
| Create reports | ✅ | ✅ | ❌ |
| View reports | ✅ | ✅ | ✅ |
| Update reports | ✅ | ✅ | ❌ |
| Delete reports | ✅ | ✅ | ❌ |
| View alerts | ✅ | ✅ | ✅ |
| Update alerts | ✅ | ✅ | ❌ |
| System config | ✅ | ❌ | ❌ |

---

## 🐛 Troubleshooting

### Issue: "JWT_SECRET_KEY is required"

**Solution:** Generate and set JWT secret key in .env

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))" >> .env
# Then add: JWT_SECRET_KEY=<generated-value>
docker compose restart backend
```

### Issue: "Could not validate credentials"

**Solution:** Token may be expired or invalid

- Access tokens expire after 15 minutes
- Use refresh token to get new access token
- Re-login if refresh token also expired

### Issue: "Account is locked"

**Solution:** Admin must unlock via API

```bash
curl -X POST "http://localhost:8000/users/{user_id}/unlock" \
  -H "Authorization: Bearer <admin_token>"
```

### Issue: "Permission denied. Required role: admin"

**Solution:** User doesn't have required role

- Check user role: `GET /auth/me`
- Admin must update role: `PATCH /users/{user_id}`

### Issue: Can't create first admin user

**Solution:** Check database connection and migration status

```bash
docker compose exec backend alembic current
# Should show: 005 (head)

docker compose exec backend python scripts/create_admin_user.py
```

---

## 🔄 Migration from Legacy API Keys

Phase 2 maintains **backward compatibility** with legacy API keys from .env:

```bash
# Legacy API keys (still work)
API_KEYS=dev-api-key-12345,another-key-67890
REQUIRE_API_KEY=false
```

**Migration Path:**

1. Create user accounts for each API key user
2. Generate per-user API keys via `/users/me/api-keys`
3. Update client applications to use new API keys
4. Disable legacy API keys: `REQUIRE_API_KEY=false`
5. Remove `API_KEYS` from .env

---

## 📊 Database Schema

### users table

```sql
id                     UUID PRIMARY KEY
username               VARCHAR(50) UNIQUE NOT NULL
email                  VARCHAR(255) UNIQUE NOT NULL
hashed_password        VARCHAR(255) NOT NULL
role                   ENUM('admin', 'analyst', 'viewer') NOT NULL
is_active              BOOLEAN DEFAULT TRUE
is_locked              BOOLEAN DEFAULT FALSE
failed_login_attempts  INTEGER DEFAULT 0
created_at             TIMESTAMP NOT NULL
updated_at             TIMESTAMP NOT NULL
last_login             TIMESTAMP
```

### user_api_keys table

```sql
id          UUID PRIMARY KEY
user_id     UUID REFERENCES users(id) ON DELETE CASCADE
key_name    VARCHAR(100) NOT NULL
key_prefix  VARCHAR(10) NOT NULL
key_hash    VARCHAR(64) UNIQUE NOT NULL  -- SHA256
is_active   BOOLEAN DEFAULT TRUE
last_used   TIMESTAMP
expires_at  TIMESTAMP
created_at  TIMESTAMP NOT NULL
```

### refresh_tokens table

```sql
id           UUID PRIMARY KEY
user_id      UUID REFERENCES users(id) ON DELETE CASCADE
token_hash   VARCHAR(64) UNIQUE NOT NULL  -- SHA256
expires_at   TIMESTAMP NOT NULL
revoked      BOOLEAN DEFAULT FALSE
revoked_at   TIMESTAMP
user_agent   VARCHAR(500)
ip_address   VARCHAR(45)
created_at   TIMESTAMP NOT NULL
```

---

## ✅ Phase 2 Checklist

- [ ] JWT secret key generated and added to .env
- [ ] Database migration 005 applied
- [ ] Backend service restarted
- [ ] First admin user created
- [ ] Login test successful (Test 1)
- [ ] Current user endpoint works (Test 2)
- [ ] Additional user created (Test 3)
- [ ] API key generation works (Test 4)
- [ ] API key authentication works (Test 5)
- [ ] Token refresh works (Test 6)
- [ ] RBAC permissions enforced (try analyst accessing /users - should fail)

---

## 📈 Next Steps

**Phase 2 is now complete!** You have a fully functional JWT authentication system with RBAC.

**Recommended next actions:**

1. ✅ Create user accounts for your team
2. ✅ Test role permissions thoroughly
3. ✅ Generate API keys for automated systems
4. ✅ Update client applications to use JWT authentication
5. 🔜 **Phase 3**: Enhanced Alerting (persistent history, Teams priority)
6. 🔜 **Phase 4**: ML Analytics (anomaly detection, geolocation)

---

## 🆘 Need Help?

- **API Docs**: http://localhost:8000/docs
- **Auth Endpoints**: http://localhost:8000/docs#/Authentication
- **User Management**: http://localhost:8000/docs#/User%20Management
- **Health Check**: `curl http://localhost:8000/health`

**Phase 2 Status**: ✅ **100% COMPLETE** (6/6 tasks)
