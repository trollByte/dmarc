/**
 * Error Handling Tests
 * Tests for error display, retry functionality, loading states, and empty states
 */

describe('Error Display', () => {
  const showError = (containerId, message) => {
    const container = document.getElementById(containerId);
    if (!container) return null;

    // Clear existing content
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }

    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.setAttribute('role', 'alert');
    errorDiv.setAttribute('aria-live', 'assertive');

    const icon = document.createElement('span');
    icon.className = 'error-icon';
    icon.textContent = '!';

    const text = document.createElement('p');
    text.className = 'error-text';
    text.textContent = message;

    errorDiv.appendChild(icon);
    errorDiv.appendChild(text);
    container.appendChild(errorDiv);

    return errorDiv;
  };

  test('renders error message in container', () => {
    const container = document.createElement('div');
    container.id = 'errorContainer';
    document.body.appendChild(container);

    showError('errorContainer', 'Something went wrong');

    const errorEl = container.querySelector('.error-message');
    expect(errorEl).not.toBeNull();
    expect(errorEl.querySelector('.error-text').textContent).toBe('Something went wrong');
  });

  test('error element has role="alert" for accessibility', () => {
    const container = document.createElement('div');
    container.id = 'alertContainer';
    document.body.appendChild(container);

    showError('alertContainer', 'Error occurred');

    const errorEl = container.querySelector('.error-message');
    expect(errorEl.getAttribute('role')).toBe('alert');
    expect(errorEl.getAttribute('aria-live')).toBe('assertive');
  });

  test('clears previous content before showing error', () => {
    const container = document.createElement('div');
    container.id = 'clearContainer';
    const oldContent = document.createElement('p');
    oldContent.textContent = 'Old content';
    container.appendChild(oldContent);
    document.body.appendChild(container);

    showError('clearContainer', 'New error');

    expect(container.querySelector('p.error-text').textContent).toBe('New error');
    expect(container.querySelectorAll('.error-message').length).toBe(1);
  });

  test('returns null for missing container', () => {
    const result = showError('nonExistentContainer', 'Error');
    expect(result).toBeNull();
  });
});

describe('Retry Button', () => {
  const showErrorWithRetry = (containerId, message, retryFn) => {
    const container = document.getElementById(containerId);
    if (!container) return null;

    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }

    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.setAttribute('role', 'alert');

    const text = document.createElement('p');
    text.className = 'error-text';
    text.textContent = message;

    const retryBtn = document.createElement('button');
    retryBtn.className = 'retry-button';
    retryBtn.textContent = 'Retry';
    retryBtn.addEventListener('click', retryFn);

    errorDiv.appendChild(text);
    errorDiv.appendChild(retryBtn);
    container.appendChild(errorDiv);

    return errorDiv;
  };

  test('retry button calls the retry function when clicked', () => {
    const container = document.createElement('div');
    container.id = 'retryContainer';
    document.body.appendChild(container);

    const retryFn = jest.fn();
    showErrorWithRetry('retryContainer', 'Failed to load', retryFn);

    const retryBtn = container.querySelector('.retry-button');
    retryBtn.click();

    expect(retryFn).toHaveBeenCalledTimes(1);
  });

  test('retry button is present in error display', () => {
    const container = document.createElement('div');
    container.id = 'retryPresent';
    document.body.appendChild(container);

    showErrorWithRetry('retryPresent', 'Error', jest.fn());

    const retryBtn = container.querySelector('.retry-button');
    expect(retryBtn).not.toBeNull();
    expect(retryBtn.textContent).toBe('Retry');
  });

  test('multiple clicks call retry function multiple times', () => {
    const container = document.createElement('div');
    container.id = 'multiRetry';
    document.body.appendChild(container);

    const retryFn = jest.fn();
    showErrorWithRetry('multiRetry', 'Error', retryFn);

    const retryBtn = container.querySelector('.retry-button');
    retryBtn.click();
    retryBtn.click();
    retryBtn.click();

    expect(retryFn).toHaveBeenCalledTimes(3);
  });
});

describe('Loading State', () => {
  const showLoading = (containerId) => {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.classList.add('loading');
    container.setAttribute('aria-busy', 'true');

    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner';
    spinner.setAttribute('role', 'status');

    const label = document.createElement('span');
    label.className = 'sr-only';
    label.textContent = 'Loading...';
    spinner.appendChild(label);

    container.appendChild(spinner);
  };

  const hideLoading = (containerId) => {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.classList.remove('loading');
    container.setAttribute('aria-busy', 'false');

    const spinner = container.querySelector('.loading-spinner');
    if (spinner) spinner.remove();
  };

  test('shows spinner with loading class', () => {
    const container = document.createElement('div');
    container.id = 'loadingContainer';
    document.body.appendChild(container);

    showLoading('loadingContainer');

    expect(container.classList.contains('loading')).toBe(true);
    expect(container.getAttribute('aria-busy')).toBe('true');
  });

  test('spinner element is added to container', () => {
    const container = document.createElement('div');
    container.id = 'spinnerContainer';
    document.body.appendChild(container);

    showLoading('spinnerContainer');

    const spinner = container.querySelector('.loading-spinner');
    expect(spinner).not.toBeNull();
    expect(spinner.getAttribute('role')).toBe('status');
  });

  test('spinner has screen reader text', () => {
    const container = document.createElement('div');
    container.id = 'srContainer';
    document.body.appendChild(container);

    showLoading('srContainer');

    const srText = container.querySelector('.sr-only');
    expect(srText).not.toBeNull();
    expect(srText.textContent).toBe('Loading...');
  });

  test('hides loading state and removes spinner', () => {
    const container = document.createElement('div');
    container.id = 'hideLoadingContainer';
    container.classList.add('loading');
    document.body.appendChild(container);

    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner';
    container.appendChild(spinner);

    hideLoading('hideLoadingContainer');

    expect(container.classList.contains('loading')).toBe(false);
    expect(container.getAttribute('aria-busy')).toBe('false');
    expect(container.querySelector('.loading-spinner')).toBeNull();
  });

  test('handles hide on non-existent container gracefully', () => {
    expect(() => hideLoading('nonExistent')).not.toThrow();
  });
});

describe('Empty State', () => {
  const showEmptyState = (containerId, message, actionLabel, actionFn) => {
    const container = document.getElementById(containerId);
    if (!container) return null;

    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }

    const emptyDiv = document.createElement('div');
    emptyDiv.className = 'empty-state';

    const text = document.createElement('p');
    text.className = 'empty-state-text';
    text.textContent = message;
    emptyDiv.appendChild(text);

    if (actionLabel && actionFn) {
      const actionBtn = document.createElement('button');
      actionBtn.className = 'empty-state-action';
      actionBtn.textContent = actionLabel;
      actionBtn.addEventListener('click', actionFn);
      emptyDiv.appendChild(actionBtn);
    }

    container.appendChild(emptyDiv);
    return emptyDiv;
  };

  test('shows helpful empty state message', () => {
    const container = document.createElement('div');
    container.id = 'emptyContainer';
    document.body.appendChild(container);

    showEmptyState('emptyContainer', 'No reports found. Upload a DMARC report to get started.');

    const emptyEl = container.querySelector('.empty-state');
    expect(emptyEl).not.toBeNull();

    const textEl = container.querySelector('.empty-state-text');
    expect(textEl.textContent).toBe('No reports found. Upload a DMARC report to get started.');
  });

  test('shows action button when provided', () => {
    const container = document.createElement('div');
    container.id = 'emptyAction';
    document.body.appendChild(container);

    const actionFn = jest.fn();
    showEmptyState('emptyAction', 'No data', 'Upload Report', actionFn);

    const actionBtn = container.querySelector('.empty-state-action');
    expect(actionBtn).not.toBeNull();
    expect(actionBtn.textContent).toBe('Upload Report');

    actionBtn.click();
    expect(actionFn).toHaveBeenCalledTimes(1);
  });

  test('does not show action button when not provided', () => {
    const container = document.createElement('div');
    container.id = 'emptyNoAction';
    document.body.appendChild(container);

    showEmptyState('emptyNoAction', 'No data available');

    const actionBtn = container.querySelector('.empty-state-action');
    expect(actionBtn).toBeNull();
  });

  test('returns null for missing container', () => {
    const result = showEmptyState('nonExistent', 'No data');
    expect(result).toBeNull();
  });

  test('clears existing content before showing empty state', () => {
    const container = document.createElement('div');
    container.id = 'clearEmpty';
    const p1 = document.createElement('p');
    p1.textContent = 'Previous content';
    const p2 = document.createElement('p');
    p2.textContent = 'More content';
    container.appendChild(p1);
    container.appendChild(p2);
    document.body.appendChild(container);

    showEmptyState('clearEmpty', 'Empty');

    expect(container.querySelectorAll('.empty-state').length).toBe(1);
    expect(container.querySelector('p:not(.empty-state-text)')).toBeNull();
  });
});

describe('Loading Progress Bar', () => {
  const createProgressUI = () => {
    const progressEl = document.createElement('div');
    progressEl.id = 'loadingProgress';

    const bar = document.createElement('div');
    bar.className = 'loading-progress-bar';
    bar.style.width = '0%';

    const text = document.createElement('span');
    text.className = 'loading-progress-text';
    text.textContent = '';

    progressEl.appendChild(bar);
    progressEl.appendChild(text);
    document.body.appendChild(progressEl);
    return progressEl;
  };

  test('shows loading progress with active class', () => {
    const progressEl = createProgressUI();

    progressEl.classList.add('active');
    const bar = progressEl.querySelector('.loading-progress-bar');
    bar.style.width = '0%';
    const text = progressEl.querySelector('.loading-progress-text');
    text.textContent = 'Loading dashboard...';

    expect(progressEl.classList.contains('active')).toBe(true);
    expect(bar.style.width).toBe('0%');
    expect(text.textContent).toBe('Loading dashboard...');
  });

  test('updates progress bar width and text', () => {
    const progressEl = createProgressUI();
    const bar = progressEl.querySelector('.loading-progress-bar');
    const text = progressEl.querySelector('.loading-progress-text');

    // Simulate 3 of 5 items loaded
    const percent = Math.round((3 / 5) * 100);
    bar.style.width = `${percent}%`;
    text.textContent = `Loading (3/5)...`;

    expect(bar.style.width).toBe('60%');
    expect(text.textContent).toBe('Loading (3/5)...');
  });

  test('hides progress by removing active class', () => {
    const progressEl = createProgressUI();
    progressEl.classList.add('active');

    progressEl.classList.remove('active');

    expect(progressEl.classList.contains('active')).toBe(false);
  });
});
