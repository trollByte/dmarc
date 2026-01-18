/**
 * API Client Tests
 * Tests for API interactions
 */

const API_BASE = '/api';

// API client helper functions
const apiClient = {
  async get(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  },

  async post(endpoint, data) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  },

  async upload(endpoint, files) {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  },
};

describe('API Client', () => {
  beforeEach(() => {
    global.fetch.mockClear();
  });

  describe('get()', () => {
    test('makes GET request to correct endpoint', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ data: 'test' }),
      });

      const result = await apiClient.get('/domains');

      expect(fetch).toHaveBeenCalledWith('/api/domains');
      expect(result).toEqual({ data: 'test' });
    });

    test('throws error on non-ok response', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      await expect(apiClient.get('/notfound')).rejects.toThrow('HTTP error! status: 404');
    });

    test('handles network errors', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(apiClient.get('/domains')).rejects.toThrow('Network error');
    });
  });

  describe('post()', () => {
    test('makes POST request with JSON body', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      const data = { domain: 'example.com' };
      const result = await apiClient.post('/filters', data);

      expect(fetch).toHaveBeenCalledWith('/api/filters', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      expect(result).toEqual({ success: true });
    });

    test('throws error on non-ok response', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
      });

      await expect(apiClient.post('/filters', {})).rejects.toThrow('HTTP error! status: 400');
    });
  });

  describe('upload()', () => {
    test('uploads files using FormData', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ uploaded: 1 }),
      });

      const file = new File(['content'], 'report.xml', { type: 'application/xml' });
      const result = await apiClient.upload('/upload', [file]);

      expect(fetch).toHaveBeenCalledWith(
        '/api/upload',
        expect.objectContaining({
          method: 'POST',
          body: expect.any(FormData),
        })
      );
      expect(result).toEqual({ uploaded: 1 });
    });

    test('handles multiple files', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ uploaded: 2 }),
      });

      const files = [
        new File(['content1'], 'report1.xml', { type: 'application/xml' }),
        new File(['content2'], 'report2.xml', { type: 'application/xml' }),
      ];

      const result = await apiClient.upload('/upload', files);

      expect(result).toEqual({ uploaded: 2 });
    });
  });
});

describe('API Endpoints', () => {
  const mockFetch = (responseData, ok = true) => {
    global.fetch.mockResolvedValueOnce({
      ok,
      status: ok ? 200 : 500,
      json: () => Promise.resolve(responseData),
    });
  };

  describe('Domains API', () => {
    test('fetches domain list', async () => {
      const mockDomains = {
        total: 2,
        domains: [
          { domain: 'example.com', report_count: 10 },
          { domain: 'test.com', report_count: 5 },
        ],
      };
      mockFetch(mockDomains);

      const result = await apiClient.get('/domains');

      expect(result.total).toBe(2);
      expect(result.domains).toHaveLength(2);
    });
  });

  describe('Reports API', () => {
    test('fetches reports with filters', async () => {
      const mockReports = {
        total: 100,
        page: 1,
        page_size: 20,
        reports: [
          { report_id: '1', domain: 'example.com' },
          { report_id: '2', domain: 'example.com' },
        ],
      };
      mockFetch(mockReports);

      const result = await apiClient.get('/reports?domain=example.com&page=1');

      expect(result.total).toBe(100);
      expect(result.reports).toHaveLength(2);
    });
  });

  describe('Summary API', () => {
    test('fetches rollup summary', async () => {
      const mockSummary = {
        total_reports: 150,
        total_messages: 50000,
        pass_count: 45000,
        fail_count: 5000,
        pass_percentage: 90,
        fail_percentage: 10,
      };
      mockFetch(mockSummary);

      const result = await apiClient.get('/rollup/summary');

      expect(result.total_reports).toBe(150);
      expect(result.pass_percentage).toBe(90);
    });
  });

  describe('Upload API', () => {
    test('uploads DMARC reports', async () => {
      const mockResponse = {
        total_files: 1,
        uploaded: 1,
        duplicates: 0,
        errors: 0,
        files: [{ filename: 'report.xml', status: 'uploaded' }],
      };
      mockFetch(mockResponse);

      const file = new File(['<xml/>'], 'report.xml', { type: 'application/xml' });
      const result = await apiClient.upload('/upload', [file]);

      expect(result.uploaded).toBe(1);
      expect(result.files[0].status).toBe('uploaded');
    });

    test('handles duplicate files', async () => {
      const mockResponse = {
        total_files: 1,
        uploaded: 0,
        duplicates: 1,
        errors: 0,
        files: [{ filename: 'report.xml', status: 'duplicate' }],
      };
      mockFetch(mockResponse);

      const file = new File(['<xml/>'], 'report.xml', { type: 'application/xml' });
      const result = await apiClient.upload('/upload', [file]);

      expect(result.duplicates).toBe(1);
      expect(result.files[0].status).toBe('duplicate');
    });
  });

  describe('Health API', () => {
    test('checks health status', async () => {
      const mockHealth = {
        status: 'healthy',
        service: 'DMARC Report Processor',
        database: 'connected',
      };
      mockFetch(mockHealth);

      const result = await apiClient.get('/healthz');

      expect(result.status).toBe('healthy');
      expect(result.database).toBe('connected');
    });
  });
});

describe('Error Handling', () => {
  test('handles 401 unauthorized', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
    });

    await expect(apiClient.get('/protected')).rejects.toThrow('HTTP error! status: 401');
  });

  test('handles 403 forbidden', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
    });

    await expect(apiClient.get('/admin')).rejects.toThrow('HTTP error! status: 403');
  });

  test('handles 500 server error', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await expect(apiClient.get('/broken')).rejects.toThrow('HTTP error! status: 500');
  });

  test('handles timeout', async () => {
    global.fetch.mockImplementationOnce(
      () => new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 100))
    );

    await expect(apiClient.get('/slow')).rejects.toThrow('Timeout');
  });
});
