# Frontend Authentication Integration Guide

This guide documents the authentication implementation in the DMARC Dashboard frontend (`frontend/js/app.js`).

## Architecture Overview

The frontend uses a **JWT-based authentication system** with:
- Login overlay for unauthenticated users
- Automatic token refresh before expiry
- Global fetch wrapper for auth header injection
- Role-based UI visibility

## Key Components

### 1. Authentication State

Global variables in `app.js`:

```javascript
let accessToken = null;        // Short-lived JWT (15 min)
let refreshToken = null;       // Long-lived JWT (7 days)
let currentUser = null;        // User profile object
let isRefreshingToken = false; // Prevents concurrent refresh calls
```

### 2. Login Overlay Flow

**Initial State:**
- On page load, no tokens exist
- `#loginOverlay` is displayed
- `#dashboardContainer` is hidden

**Login Process:**

```javascript
async function login(username, password) {
  // 1. Disable submit button and show loading state
  submitBtn.disabled = true;
  submitBtn.textContent = 'Signing in...';

  // 2. Call login API
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });

  // 3. Store tokens
  const data = await response.json();
  accessToken = data.access_token;
  refreshToken = data.refresh_token;

  // 4. Fetch user profile
  await fetchCurrentUser();

  // 5. Hide overlay and show dashboard
  hideLoginOverlay();
  updateUserMenu();
  updateSidebarUser();
  initSidebarAndRouter();
}
```

**HTML Structure:**

```html
<div id="loginOverlay" class="login-overlay">
  <div class="login-container">
    <h1>DMARC Dashboard</h1>
    <form id="loginForm">
      <input type="text" id="loginUsername" placeholder="Username" required>
      <input type="password" id="loginPassword" placeholder="Password" required>
      <div id="loginError" class="error-message" hidden></div>
      <button type="submit" id="loginSubmitBtn">Sign In</button>
    </form>
  </div>
</div>
```

**Event Handler:**

```javascript
document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('loginUsername').value;
  const password = document.getElementById('loginPassword').value;
  await login(username, password);
});
```

### 3. Token Management

#### Storing Tokens

Currently stored in **memory** (global variables):
- Pros: Secure from XSS (not in localStorage/cookies)
- Cons: Lost on page refresh

**Production Considerations:**

For persistent sessions, consider:
- **httpOnly cookies** (backend sets `Set-Cookie` on login)
- **sessionStorage** (cleared on tab close)
- **localStorage** (persists across tabs, but XSS vulnerable)

#### Fetching User Profile

```javascript
async function fetchCurrentUser() {
  const response = await fetch(`${API_BASE}/auth/me`, {
    headers: getAuthHeaders()
  });

  if (response.ok) {
    const data = await response.json();
    currentUser = data.user || data;
  }
}
```

**User Profile Structure:**

```javascript
{
  id: "550e8400-e29b-41d4-a716-446655440000",
  username: "admin",
  email: "admin@example.com",
  role: "admin",          // "admin" | "analyst" | "viewer"
  is_active: true,
  totp_enabled: false,
  created_at: "2026-01-01T00:00:00Z",
  last_login: "2026-02-06T12:00:00Z"
}
```

### 4. Auto-Refresh Mechanism

The frontend **automatically refreshes** the access token when API calls return 401.

#### Global Fetch Wrapper

```javascript
const _originalFetch = window.fetch;

window.fetch = async function(url, options = {}) {
  const urlStr = typeof url === 'string' ? url : url.toString();
  const isApiCall = urlStr.startsWith(API_BASE) || urlStr.startsWith('/api');
  const isAuthEndpoint = urlStr.includes('/auth/login') || urlStr.includes('/auth/refresh');

  // 1. Inject auth headers for API calls (except login/refresh)
  if (isApiCall && !isAuthEndpoint && accessToken) {
    options.headers = {
      ...options.headers,
      ...getAuthHeaders()
    };
  }

  // 2. Make the request
  let response = await _originalFetch.call(window, url, options);

  // 3. If 401, try refreshing token once
  if (response.status === 401 && isApiCall && !isAuthEndpoint && refreshToken) {
    const refreshed = await refreshAccessToken();

    if (refreshed) {
      // Retry with new token
      options.headers = {
        ...options.headers,
        ...getAuthHeaders()
      };
      response = await _originalFetch.call(window, url, options);
    }
  }

  return response;
};
```

#### Refresh Token Flow

```javascript
async function refreshAccessToken() {
  // Prevent concurrent refresh calls
  if (isRefreshingToken || !refreshToken) return false;
  isRefreshingToken = true;

  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    });

    if (!response.ok) {
      // Refresh failed - force re-login
      accessToken = null;
      refreshToken = null;
      currentUser = null;
      showLoginOverlay();
      updateUserMenu();
      return false;
    }

    const data = await response.json();
    accessToken = data.access_token;
    return true;
  } catch (e) {
    return false;
  } finally {
    isRefreshingToken = false;
  }
}
```

**Flow Diagram:**

```
API Call → 401 → refreshAccessToken()
                    ├─ Success → Retry with new token
                    └─ Failure → Show login overlay
```

### 5. Logout

```javascript
async function logout() {
  try {
    // 1. Revoke refresh token on backend (best-effort)
    if (accessToken && refreshToken) {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify({ refresh_token: refreshToken })
      });
    }
  } catch (e) {
    // Logout API call is best-effort
  }

  // 2. Clear local state
  accessToken = null;
  refreshToken = null;
  currentUser = null;

  // 3. Show login overlay
  showLoginOverlay();
  updateUserMenu();
  resetSidebarAndRouter();

  // 4. Clear login form
  document.getElementById('loginUsername').value = '';
  document.getElementById('loginPassword').value = '';
  document.getElementById('loginError').hidden = true;
}
```

**Logout Button Handler:**

```javascript
document.getElementById('logoutBtn')?.addEventListener('click', async () => {
  await logout();
});
```

### 6. Role-Based UI Visibility

The frontend shows/hides UI elements based on `currentUser.role`.

**User Roles:**
- `admin` - Full access: user management, system config
- `analyst` - Read/write: reports, alerts
- `viewer` - Read-only access

**Example Implementations:**

```javascript
function updateUserMenu() {
  const userMenu = document.getElementById('userMenu');
  const displayName = document.getElementById('userDisplayName');
  const menuUsername = document.getElementById('userMenuUsername');
  const menuRole = document.getElementById('userMenuRole');

  if (currentUser && userMenu) {
    userMenu.hidden = false;
    displayName.textContent = currentUser.username || '';
    menuUsername.textContent = currentUser.username || '';
    menuRole.textContent = currentUser.role || '';
  } else if (userMenu) {
    userMenu.hidden = true;
  }
}

function updateSidebarUser() {
  const usernameEl = document.getElementById('sidebarUsername');
  const roleEl = document.getElementById('sidebarRole');

  if (currentUser) {
    if (usernameEl) usernameEl.textContent = currentUser.username;
    if (roleEl) roleEl.textContent = currentUser.role.toUpperCase();
  }
}
```

**Conditional Rendering:**

```javascript
// Show admin-only features
if (currentUser?.role === 'admin') {
  document.querySelector('[data-page="users"]').hidden = false;
  document.querySelector('[data-page="settings"]').hidden = false;
} else {
  document.querySelector('[data-page="users"]').hidden = true;
  document.querySelector('[data-page="settings"]').hidden = true;
}

// Disable edit buttons for viewers
if (currentUser?.role === 'viewer') {
  document.querySelectorAll('.edit-btn, .delete-btn').forEach(btn => {
    btn.disabled = true;
    btn.title = 'View-only access';
  });
}
```

## Session Management

### Session Lifetime

- **Access Token:** 15 minutes
- **Refresh Token:** 7 days
- **Session expires:** After 7 days or on logout

### Session Persistence

**Current Implementation:**
- Tokens stored in memory
- Lost on page refresh → User must re-login

**Alternative Approaches:**

**1. LocalStorage (Persistent, XSS vulnerable):**

```javascript
// Store tokens
localStorage.setItem('dmarc_access_token', accessToken);
localStorage.setItem('dmarc_refresh_token', refreshToken);

// Load on page load
accessToken = localStorage.getItem('dmarc_access_token');
refreshToken = localStorage.getItem('dmarc_refresh_token');

// Clear on logout
localStorage.removeItem('dmarc_access_token');
localStorage.removeItem('dmarc_refresh_token');
```

**2. SessionStorage (Tab-scoped):**

```javascript
// Store tokens
sessionStorage.setItem('dmarc_access_token', accessToken);
sessionStorage.setItem('dmarc_refresh_token', refreshToken);
```

**3. httpOnly Cookies (Most secure, requires backend changes):**

```python
# Backend: Set cookie on login
response.set_cookie(
    key="refresh_token",
    value=refresh_token,
    httponly=True,
    secure=True,  # HTTPS only
    samesite="strict",
    max_age=7 * 24 * 60 * 60  # 7 days
)
```

```javascript
// Frontend: Browser automatically sends cookie
// No need to manually manage refresh_token
```

## Error Handling

### Authentication Errors

```javascript
async function login(username, password) {
  const errorEl = document.getElementById('loginError');
  errorEl.hidden = true;

  try {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Invalid credentials');
    }

    // Success flow...
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  }
}
```

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Incorrect username or password" | Invalid credentials | Check username/password |
| "Two-factor authentication required" | 2FA enabled | Prompt for TOTP code |
| "Account is inactive" | User disabled | Contact admin |
| "Account is locked" | Too many failed logins | Contact admin or wait |
| "Token has expired" | Access token expired | Auto-refresh triggered |
| "Invalid refresh token" | Refresh token invalid/expired | Force re-login |

### Network Error Handling

```javascript
try {
  const response = await fetch('/api/reports');
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = await response.json();
  // Use data...
} catch (err) {
  if (err.name === 'TypeError') {
    // Network error
    showNotification('Network error. Please check your connection.', 'error');
  } else {
    showNotification(`Error: ${err.message}`, 'error');
  }
}
```

## Two-Factor Authentication (2FA)

### 2FA Login Flow

**1. Detect 2FA Required:**

```javascript
const response = await fetch(`${API_BASE}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
});

if (response.status === 401) {
  const requires2FA = response.headers.get('X-2FA-Required') === 'true';
  if (requires2FA) {
    // Show TOTP input
    show2FAPrompt();
    return;
  }
}
```

**2. Prompt for TOTP Code:**

```html
<div id="totp-prompt" hidden>
  <label for="totp-code">Enter 6-digit code from authenticator app:</label>
  <input type="text" id="totp-code" maxlength="6" pattern="[0-9]{6}" required>
  <button onclick="loginWith2FA()">Verify</button>
</div>
```

**3. Submit with TOTP:**

```javascript
async function loginWith2FA() {
  const totpCode = document.getElementById('totp-code').value;

  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      password,
      totp_code: totpCode
    })
  });

  // Handle response...
}
```

## Security Best Practices

### 1. Token Storage
- **Avoid localStorage** for sensitive tokens (XSS vulnerable)
- **Prefer memory or httpOnly cookies**
- Never log tokens to console

### 2. HTTPS Enforcement
```javascript
if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
  console.warn('WARNING: Running over HTTP. Tokens are vulnerable to interception.');
}
```

### 3. Token Expiry Handling
- Implement auto-refresh before 401 errors
- Check `expires_in` and refresh proactively

### 4. CSRF Protection
- Use `SameSite` cookies
- Validate Origin headers
- Implement CSRF tokens for state-changing requests

### 5. Content Security Policy
```javascript
// Already implemented in backend middleware
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';
```

## Testing Authentication

### Manual Testing

**1. Login/Logout:**
```javascript
// Open browser console
await login('admin', 'password');
console.log('Access token:', accessToken);
console.log('Current user:', currentUser);

await logout();
console.log('Tokens cleared:', accessToken === null);
```

**2. Token Refresh:**
```javascript
// Wait 15 minutes for access token to expire
// Or manually expire it
accessToken = 'expired_token';

// Make an API call - should auto-refresh
const response = await fetch('/api/reports');
console.log('Auto-refresh worked:', response.ok);
```

### Automated Testing

See `e2e/tests/auth.spec.js` for end-to-end authentication tests:
- Login success/failure
- Token refresh
- Logout
- Protected page access
- Role-based visibility

## Troubleshooting

### Login Overlay Won't Hide

**Symptoms:** Login succeeds but overlay remains visible.

**Causes:**
1. `hideLoginOverlay()` not called
2. CSS `display` property not set correctly
3. JavaScript error preventing execution

**Debug:**
```javascript
console.log('Login overlay display:', document.getElementById('loginOverlay').style.display);
console.log('Access token exists:', !!accessToken);
console.log('Current user:', currentUser);
```

### Infinite Refresh Loop

**Symptoms:** Continuous refresh calls, browser hangs.

**Causes:**
1. `isRefreshingToken` flag not working
2. Refresh endpoint also returning 401

**Debug:**
```javascript
console.log('Is refreshing:', isRefreshingToken);
console.log('Refresh token:', refreshToken);

// Test refresh endpoint directly
const response = await fetch('/api/auth/refresh', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ refresh_token: refreshToken })
});
console.log('Refresh response:', response.status);
```

### User Role Not Applied

**Symptoms:** Admin features hidden for admin user.

**Causes:**
1. `currentUser` not populated
2. Role check logic incorrect
3. Timing issue (UI updated before user fetched)

**Debug:**
```javascript
console.log('Current user role:', currentUser?.role);
console.log('Expected role:', 'admin');

// Check UI elements
document.querySelectorAll('[data-role-required]').forEach(el => {
  console.log('Element:', el, 'Required role:', el.dataset.roleRequired);
});
```

## See Also

- [API Authentication Guide](api-auth.md) - Backend authentication details
- [User Guide](USER_GUIDE.md) - End-user documentation
- `/frontend/js/app.js` - Full implementation source code
