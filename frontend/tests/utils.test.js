/**
 * Utility Function Tests
 * Tests for utility functions extracted from app.js
 */

describe('Utility Functions', () => {
  describe('formatNumber', () => {
    // Inline implementation for testing
    const formatNumber = (num) => {
      if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
      } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
      }
      return num.toString();
    };

    test('formats millions correctly', () => {
      expect(formatNumber(1000000)).toBe('1.0M');
      expect(formatNumber(2500000)).toBe('2.5M');
      expect(formatNumber(10000000)).toBe('10.0M');
    });

    test('formats thousands correctly', () => {
      expect(formatNumber(1000)).toBe('1.0K');
      expect(formatNumber(2500)).toBe('2.5K');
      expect(formatNumber(99999)).toBe('100.0K');
    });

    test('returns numbers below 1000 as-is', () => {
      expect(formatNumber(0)).toBe('0');
      expect(formatNumber(100)).toBe('100');
      expect(formatNumber(999)).toBe('999');
    });
  });

  describe('formatDate', () => {
    const formatDate = (dateStr) => {
      if (!dateStr) return '-';
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    };

    test('formats ISO date string correctly', () => {
      const result = formatDate('2024-01-15T12:00:00Z');
      expect(result).toMatch(/Jan 15, 2024/);
    });

    test('returns dash for empty input', () => {
      expect(formatDate('')).toBe('-');
      expect(formatDate(null)).toBe('-');
      expect(formatDate(undefined)).toBe('-');
    });
  });

  describe('formatPercentage', () => {
    const formatPercentage = (value, decimals = 1) => {
      if (value === null || value === undefined || isNaN(value)) return '-';
      return value.toFixed(decimals) + '%';
    };

    test('formats percentages correctly', () => {
      expect(formatPercentage(75.5)).toBe('75.5%');
      expect(formatPercentage(100)).toBe('100.0%');
      expect(formatPercentage(0)).toBe('0.0%');
    });

    test('handles custom decimal places', () => {
      expect(formatPercentage(75.555, 2)).toBe('75.56%');
      expect(formatPercentage(75.5, 0)).toBe('76%');
    });

    test('returns dash for invalid input', () => {
      expect(formatPercentage(null)).toBe('-');
      expect(formatPercentage(undefined)).toBe('-');
      expect(formatPercentage(NaN)).toBe('-');
    });
  });

  describe('debounce', () => {
    jest.useFakeTimers();

    const debounce = (func, wait) => {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout);
          func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
      };
    };

    test('debounces function calls', () => {
      const mockFn = jest.fn();
      const debouncedFn = debounce(mockFn, 100);

      debouncedFn();
      debouncedFn();
      debouncedFn();

      expect(mockFn).not.toHaveBeenCalled();

      jest.advanceTimersByTime(100);

      expect(mockFn).toHaveBeenCalledTimes(1);
    });

    test('passes arguments to debounced function', () => {
      const mockFn = jest.fn();
      const debouncedFn = debounce(mockFn, 100);

      debouncedFn('arg1', 'arg2');
      jest.advanceTimersByTime(100);

      expect(mockFn).toHaveBeenCalledWith('arg1', 'arg2');
    });
  });
});

describe('Filter Functions', () => {
  describe('buildQueryString', () => {
    const buildQueryString = (filters) => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== '' && value !== null && value !== undefined) {
          params.append(key, value);
        }
      });
      return params.toString();
    };

    test('builds query string from filters', () => {
      const filters = {
        domain: 'example.com',
        days: 30,
      };
      const result = buildQueryString(filters);
      expect(result).toContain('domain=example.com');
      expect(result).toContain('days=30');
    });

    test('skips empty values', () => {
      const filters = {
        domain: 'example.com',
        empty: '',
        nullVal: null,
        undefinedVal: undefined,
      };
      const result = buildQueryString(filters);
      expect(result).toBe('domain=example.com');
    });

    test('handles empty filters', () => {
      expect(buildQueryString({})).toBe('');
    });
  });

  describe('parseFiltersFromUrl', () => {
    const parseFiltersFromUrl = () => {
      const params = new URLSearchParams(window.location.search);
      return {
        domain: params.get('domain') || '',
        days: parseInt(params.get('days'), 10) || 365,
        sourceIp: params.get('sourceIp') || '',
      };
    };

    test('parses URL parameters', () => {
      delete window.location;
      window.location = { search: '?domain=test.com&days=30' };

      const filters = parseFiltersFromUrl();
      expect(filters.domain).toBe('test.com');
      expect(filters.days).toBe(30);
    });

    test('returns defaults for missing params', () => {
      delete window.location;
      window.location = { search: '' };

      const filters = parseFiltersFromUrl();
      expect(filters.domain).toBe('');
      expect(filters.days).toBe(365);
    });
  });
});

describe('Data Processing', () => {
  describe('calculatePassRate', () => {
    const calculatePassRate = (passed, total) => {
      if (!total || total === 0) return 0;
      return (passed / total) * 100;
    };

    test('calculates pass rate correctly', () => {
      expect(calculatePassRate(75, 100)).toBe(75);
      expect(calculatePassRate(30, 60)).toBe(50);
      expect(calculatePassRate(100, 100)).toBe(100);
    });

    test('handles zero total', () => {
      expect(calculatePassRate(0, 0)).toBe(0);
      expect(calculatePassRate(50, 0)).toBe(0);
    });

    test('handles edge cases', () => {
      expect(calculatePassRate(0, 100)).toBe(0);
      expect(calculatePassRate(null, 100)).toBe(0);
    });
  });

  describe('aggregateByDomain', () => {
    const aggregateByDomain = (records) => {
      const byDomain = {};
      records.forEach((record) => {
        const domain = record.domain || 'unknown';
        if (!byDomain[domain]) {
          byDomain[domain] = { count: 0, passed: 0, failed: 0 };
        }
        byDomain[domain].count += record.count || 1;
        if (record.passed) byDomain[domain].passed += record.count || 1;
        else byDomain[domain].failed += record.count || 1;
      });
      return byDomain;
    };

    test('aggregates records by domain', () => {
      const records = [
        { domain: 'a.com', count: 10, passed: true },
        { domain: 'a.com', count: 5, passed: false },
        { domain: 'b.com', count: 20, passed: true },
      ];

      const result = aggregateByDomain(records);
      expect(result['a.com'].count).toBe(15);
      expect(result['a.com'].passed).toBe(10);
      expect(result['a.com'].failed).toBe(5);
      expect(result['b.com'].count).toBe(20);
    });

    test('handles empty array', () => {
      expect(aggregateByDomain([])).toEqual({});
    });
  });
});

describe('Validation Functions', () => {
  describe('isValidDomain', () => {
    const isValidDomain = (domain) => {
      if (!domain) return false;
      const domainRegex = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$/;
      return domainRegex.test(domain);
    };

    test('validates correct domains', () => {
      expect(isValidDomain('example.com')).toBe(true);
      expect(isValidDomain('sub.example.com')).toBe(true);
      expect(isValidDomain('my-domain.co.uk')).toBe(true);
    });

    test('rejects invalid domains', () => {
      expect(isValidDomain('')).toBe(false);
      expect(isValidDomain('invalid')).toBe(false);
      expect(isValidDomain('-invalid.com')).toBe(false);
      expect(isValidDomain('invalid-.com')).toBe(false);
    });
  });

  describe('isValidIpAddress', () => {
    const isValidIpAddress = (ip) => {
      if (!ip) return false;
      // IPv4
      const ipv4Regex = /^(\d{1,3}\.){3}\d{1,3}$/;
      if (ipv4Regex.test(ip)) {
        return ip.split('.').every((part) => parseInt(part, 10) <= 255);
      }
      // IPv6 (simplified check)
      const ipv6Regex = /^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$/;
      return ipv6Regex.test(ip);
    };

    test('validates IPv4 addresses', () => {
      expect(isValidIpAddress('192.168.1.1')).toBe(true);
      expect(isValidIpAddress('0.0.0.0')).toBe(true);
      expect(isValidIpAddress('255.255.255.255')).toBe(true);
    });

    test('rejects invalid IPv4 addresses', () => {
      expect(isValidIpAddress('256.1.1.1')).toBe(false);
      expect(isValidIpAddress('1.1.1')).toBe(false);
      expect(isValidIpAddress('')).toBe(false);
    });

    test('validates IPv6 addresses', () => {
      expect(isValidIpAddress('2001:db8::1')).toBe(true);
      expect(isValidIpAddress('::1')).toBe(true);
    });
  });
});
