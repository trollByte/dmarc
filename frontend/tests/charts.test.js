/**
 * Chart Component Tests
 * Tests for chart creation, updating, data formatting, and theme-aware colors
 */

describe('Chart Creation', () => {
  // Inline chart creation function matching app.js patterns
  const createChart = (canvasId, type, data, options = {}) => {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const ctx = canvas.getContext('2d');
    return new Chart(ctx, { type, data, options });
  };

  const setupCanvas = (id) => {
    const canvas = document.createElement('canvas');
    canvas.id = id;
    canvas.getContext = jest.fn(() => ({
      clearRect: jest.fn(),
      fillRect: jest.fn(),
    }));
    document.body.appendChild(canvas);
    return canvas;
  };

  test('createChart returns a Chart instance for a valid canvas', () => {
    setupCanvas('timelineChart');

    const data = {
      labels: ['Jan', 'Feb', 'Mar'],
      datasets: [{ label: 'Messages', data: [100, 200, 300] }],
    };

    const chart = createChart('timelineChart', 'line', data);
    expect(chart).toBeDefined();
    expect(Chart).toHaveBeenCalled();
  });

  test('createChart returns null for missing canvas', () => {
    const chart = createChart('nonExistentChart', 'bar', { labels: [], datasets: [] });
    expect(chart).toBeNull();
  });

  test('Chart constructor receives correct type and data', () => {
    setupCanvas('domainChart');

    const data = {
      labels: ['example.com', 'test.com'],
      datasets: [{ label: 'Reports', data: [50, 30] }],
    };
    const options = { responsive: true };

    createChart('domainChart', 'bar', data, options);

    expect(Chart).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        type: 'bar',
        data,
        options,
      })
    );
  });

  test('Chart constructor called with pie type for disposition chart', () => {
    setupCanvas('dispositionChart');

    const data = {
      labels: ['none', 'quarantine', 'reject'],
      datasets: [{ data: [70, 20, 10] }],
    };

    createChart('dispositionChart', 'pie', data);

    expect(Chart).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ type: 'pie' })
    );
  });
});

describe('Chart Data Formatting', () => {
  const formatChartData = (rawData, labelKey, valueKey) => {
    if (!rawData || !Array.isArray(rawData)) return { labels: [], datasets: [] };

    const labels = rawData.map((item) => item[labelKey] || 'Unknown');
    const values = rawData.map((item) => item[valueKey] || 0);

    return {
      labels,
      datasets: [{ data: values }],
    };
  };

  test('formats raw data into chart labels and datasets', () => {
    const rawData = [
      { domain: 'example.com', count: 100 },
      { domain: 'test.com', count: 50 },
    ];

    const result = formatChartData(rawData, 'domain', 'count');

    expect(result.labels).toEqual(['example.com', 'test.com']);
    expect(result.datasets[0].data).toEqual([100, 50]);
  });

  test('handles missing keys with defaults', () => {
    const rawData = [{ domain: 'example.com' }, { count: 50 }];

    const result = formatChartData(rawData, 'domain', 'count');

    expect(result.labels).toEqual(['example.com', 'Unknown']);
    expect(result.datasets[0].data).toEqual([0, 50]);
  });

  test('returns empty structure for null input', () => {
    const result = formatChartData(null, 'domain', 'count');

    expect(result.labels).toEqual([]);
    expect(result.datasets).toEqual([]);
  });

  test('returns empty structure for non-array input', () => {
    const result = formatChartData('invalid', 'domain', 'count');

    expect(result.labels).toEqual([]);
    expect(result.datasets).toEqual([]);
  });
});

describe('Chart Update', () => {
  const updateChart = (existingChart, canvasId, type, data, options = {}) => {
    if (existingChart) {
      existingChart.destroy();
    }

    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const ctx = canvas.getContext('2d');
    return new Chart(ctx, { type, data, options });
  };

  const setupCanvas = (id) => {
    const canvas = document.createElement('canvas');
    canvas.id = id;
    canvas.getContext = jest.fn(() => ({
      clearRect: jest.fn(),
    }));
    document.body.appendChild(canvas);
    return canvas;
  };

  test('destroys existing chart before creating new one', () => {
    setupCanvas('updateTestChart');

    const mockExistingChart = {
      destroy: jest.fn(),
      update: jest.fn(),
    };

    const data = { labels: ['A'], datasets: [{ data: [1] }] };

    updateChart(mockExistingChart, 'updateTestChart', 'bar', data);

    expect(mockExistingChart.destroy).toHaveBeenCalledTimes(1);
    expect(Chart).toHaveBeenCalled();
  });

  test('creates chart without destroying when no existing chart', () => {
    setupCanvas('freshChart');

    const data = { labels: ['A'], datasets: [{ data: [1] }] };

    const chart = updateChart(null, 'freshChart', 'line', data);

    expect(chart).toBeDefined();
    expect(Chart).toHaveBeenCalled();
  });
});

describe('Theme-Aware Chart Colors', () => {
  const getChartColors = (theme) => {
    if (theme === 'dark') {
      return {
        textColor: '#e8e8e8',
        gridColor: '#2d4a6f',
        passColor: 'rgba(52, 211, 153, 0.8)',
        failColor: 'rgba(248, 113, 113, 0.8)',
      };
    }
    return {
      textColor: '#333333',
      gridColor: '#e0e0e0',
      passColor: 'rgba(16, 185, 129, 0.8)',
      failColor: 'rgba(239, 68, 68, 0.8)',
    };
  };

  test('returns light theme colors by default', () => {
    const colors = getChartColors('light');

    expect(colors.textColor).toBe('#333333');
    expect(colors.gridColor).toBe('#e0e0e0');
    expect(colors.passColor).toContain('rgba');
    expect(colors.failColor).toContain('rgba');
  });

  test('returns dark theme colors for dark mode', () => {
    const colors = getChartColors('dark');

    expect(colors.textColor).toBe('#e8e8e8');
    expect(colors.gridColor).toBe('#2d4a6f');
  });

  test('light and dark colors are different', () => {
    const lightColors = getChartColors('light');
    const darkColors = getChartColors('dark');

    expect(lightColors.textColor).not.toBe(darkColors.textColor);
    expect(lightColors.gridColor).not.toBe(darkColors.gridColor);
  });

  test('updateChartTheme applies colors to chart options', () => {
    const updateChartTheme = (chart, theme) => {
      const colors = getChartColors(theme);

      if (chart && chart.options) {
        if (chart.options.scales?.x) {
          chart.options.scales.x.ticks = { color: colors.textColor };
          chart.options.scales.x.grid = { color: colors.gridColor };
        }
        if (chart.options.scales?.y) {
          chart.options.scales.y.ticks = { color: colors.textColor };
          chart.options.scales.y.grid = { color: colors.gridColor };
        }
        if (chart.options.plugins?.legend) {
          chart.options.plugins.legend.labels = { color: colors.textColor };
        }
        chart.update();
      }
    };

    const mockChart = {
      options: {
        scales: {
          x: { ticks: {}, grid: {} },
          y: { ticks: {}, grid: {} },
        },
        plugins: {
          legend: { labels: {} },
        },
      },
      update: jest.fn(),
    };

    updateChartTheme(mockChart, 'dark');

    expect(mockChart.options.scales.x.ticks.color).toBe('#e8e8e8');
    expect(mockChart.options.scales.x.grid.color).toBe('#2d4a6f');
    expect(mockChart.options.scales.y.ticks.color).toBe('#e8e8e8');
    expect(mockChart.options.plugins.legend.labels.color).toBe('#e8e8e8');
    expect(mockChart.update).toHaveBeenCalledTimes(1);
  });
});
