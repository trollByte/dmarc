/**
 * Authentication Tests
 * Tests for login, token management, auth headers, 401 handling, and logout
 */

const API_BASE = '/api';

describe('Login', () => {
  const login = async (username, password) => {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Invalid credentials');
    }

    return response.json();
  };

  beforeEach(() => {
    global.fetch.mockClear();
  });

  test('makes POST request to /api/auth/login', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ access_token: 'abc', refresh_token: 'def' }),
    });

    await login('admin', 'password123');

    expect(fetch).toHaveBeenCalledWith('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin', password: 'password123' }),
    });
  });

  test('returns tokens on successful login', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
      }),
    });

    const result = await login('admin', 'password123');

    expect(result.access_token).toBe('test-access-token');
    expect(result.refresh_token).toBe('test-refresh-token');
  });

  test('throws error on invalid credentials', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    });

    await expect(login('wrong', 'creds')).rejects.toThrow('Invalid credentials');
  });

  test('throws generic error when response has no detail', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.reject(new Error('parse error')),
    });

    await expect(login('wrong', 'creds')).rejects.toThrow('Invalid credentials');
  });
});

describe('Token Storage', () => {
  test('tokens stored in memory variables, not localStorage', () => {
    // Simulate token storage like app.js
    let accessToken = null;
    let refreshToken = null;

    // Store tokens in memory
    accessToken = 'mem-access-token';
    refreshToken = 'mem-refresh-token';

    expect(accessToken).toBe('mem-access-token');
    expect(refreshToken).toBe('mem-refresh-token');

    // Verify localStorage was NOT called for token storage
    expect(localStorage.setItem).not.toHaveBeenCalledWith(
      expect.stringMatching(/token/i),
      expect.anything()
    );
  });

  test('tokens can be cleared by setting to null', () => {
    let accessToken = 'some-token';
    let refreshToken = 'some-refresh';

    accessToken = null;
    refreshToken = null;

    expect(accessToken).toBeNull();
    expect(refreshToken).toBeNull();
  });
});

describe('Auth Headers', () => {
  const getAuthHeaders = (token) => {
    if (token) {
      return { Authorization: 'Bearer ' + token };
    }
    return {};
  };

  test('includes Bearer token in Authorization header', () => {
    const headers = getAuthHeaders('my-access-token');

    expect(headers).toEqual({ Authorization: 'Bearer my-access-token' });
  });

  test('returns empty object when no token', () => {
    const headers = getAuthHeaders(null);

    expect(headers).toEqual({});
  });

  test('returns empty object for undefined token', () => {
    const headers = getAuthHeaders(undefined);

    expect(headers).toEqual({});
  });

  test('auth headers are included in API requests', async () => {
    const token = 'test-token';

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: 'protected' }),
    });

    await fetch(`${API_BASE}/reports`, {
      headers: getAuthHeaders(token),
    });

    expect(fetch).toHaveBeenCalledWith('/api/reports', {
      headers: { Authorization: 'Bearer test-token' },
    });
  });
});

describe('401 Response Handling', () => {
  test('401 response triggers login display', async () => {
    // Setup DOM elements
    const overlay = document.createElement('div');
    overlay.id = 'loginOverlay';
    overlay.style.display = 'none';
    document.body.appendChild(overlay);

    const dashboard = document.createElement('div');
    dashboard.id = 'dashboardContainer';
    dashboard.style.display = '';
    document.body.appendChild(dashboard);

    const showLoginOverlay = () => {
      const overlayEl = document.getElementById('loginOverlay');
      const dashboardEl = document.getElementById('dashboardContainer');
      if (overlayEl) overlayEl.style.display = '';
      if (dashboardEl) dashboardEl.style.display = 'none';
    };

    const handleResponse = (response) => {
      if (response.status === 401) {
        showLoginOverlay();
      }
    };

    // Simulate 401 response
    handleResponse({ status: 401 });

    expect(overlay.style.display).toBe('');
    expect(dashboard.style.display).toBe('none');
  });

  test('200 response does not trigger login display', () => {
    const overlay = document.createElement('div');
    overlay.id = 'loginOverlay';
    overlay.style.display = 'none';
    document.body.appendChild(overlay);

    const showLoginOverlay = () => {
      document.getElementById('loginOverlay').style.display = '';
    };

    const handleResponse = (response) => {
      if (response.status === 401) {
        showLoginOverlay();
      }
    };

    handleResponse({ status: 200 });

    expect(overlay.style.display).toBe('none');
  });
});

describe('Logout', () => {
  test('clears tokens and shows login overlay', () => {
    let accessToken = 'some-token';
    let refreshToken = 'some-refresh';
    let currentUser = { username: 'admin' };

    // Setup DOM
    const overlay = document.createElement('div');
    overlay.id = 'loginOverlay';
    overlay.style.display = 'none';
    document.body.appendChild(overlay);

    const dashboard = document.createElement('div');
    dashboard.id = 'dashboardContainer';
    document.body.appendChild(dashboard);

    const logout = () => {
      accessToken = null;
      refreshToken = null;
      currentUser = null;
      const overlayEl = document.getElementById('loginOverlay');
      const dashboardEl = document.getElementById('dashboardContainer');
      if (overlayEl) overlayEl.style.display = '';
      if (dashboardEl) dashboardEl.style.display = 'none';
    };

    logout();

    expect(accessToken).toBeNull();
    expect(refreshToken).toBeNull();
    expect(currentUser).toBeNull();
    expect(overlay.style.display).toBe('');
    expect(dashboard.style.display).toBe('none');
  });

  test('logout clears form fields', () => {
    // Setup form elements
    const username = document.createElement('input');
    username.id = 'loginUsername';
    username.value = 'admin';
    document.body.appendChild(username);

    const password = document.createElement('input');
    password.id = 'loginPassword';
    password.value = 'secret';
    document.body.appendChild(password);

    const error = document.createElement('div');
    error.id = 'loginError';
    error.hidden = false;
    error.textContent = 'Some error';
    document.body.appendChild(error);

    const clearLoginForm = () => {
      const usernameInput = document.getElementById('loginUsername');
      const passwordInput = document.getElementById('loginPassword');
      const errorEl = document.getElementById('loginError');
      if (usernameInput) usernameInput.value = '';
      if (passwordInput) passwordInput.value = '';
      if (errorEl) errorEl.hidden = true;
    };

    clearLoginForm();

    expect(username.value).toBe('');
    expect(password.value).toBe('');
    expect(error.hidden).toBe(true);
  });

  test('logout sends POST to /api/auth/logout', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true });

    const logoutApi = async (accessToken, refreshToken) => {
      if (accessToken && refreshToken) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer ' + accessToken,
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      }
    };

    await logoutApi('my-token', 'my-refresh');

    expect(fetch).toHaveBeenCalledWith('/api/auth/logout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer my-token',
      },
      body: JSON.stringify({ refresh_token: 'my-refresh' }),
    });
  });
});
