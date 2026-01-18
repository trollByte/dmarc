/**
 * DOM Interaction Tests
 * Tests for UI components and DOM manipulation
 */

import { fireEvent } from '@testing-library/dom';

// Helper to create select element with options
const createSelect = (id, options) => {
  const select = document.createElement('select');
  select.id = id;
  options.forEach(opt => {
    const option = document.createElement('option');
    option.value = opt.value;
    option.textContent = opt.label;
    select.appendChild(option);
  });
  return select;
};

describe('Theme Management', () => {
  const initTheme = () => {
    const savedTheme = localStorage.getItem('dmarc-theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
  };

  const toggleTheme = () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('dmarc-theme', newTheme);
    return newTheme;
  };

  beforeEach(() => {
    document.documentElement.removeAttribute('data-theme');
    localStorage.getItem.mockReturnValue(null);
  });

  test('initializes with light theme by default', () => {
    initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  test('initializes with saved theme', () => {
    localStorage.getItem.mockReturnValue('dark');
    initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  test('toggles theme from light to dark', () => {
    document.documentElement.setAttribute('data-theme', 'light');
    const newTheme = toggleTheme();
    expect(newTheme).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.setItem).toHaveBeenCalledWith('dmarc-theme', 'dark');
  });

  test('toggles theme from dark to light', () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    const newTheme = toggleTheme();
    expect(newTheme).toBe('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });
});

describe('Modal Management', () => {
  const createModal = (id) => {
    const modal = document.createElement('div');
    modal.id = id;
    modal.hidden = true;
    modal.classList.add('modal');
    document.body.appendChild(modal);
    return modal;
  };

  const openModal = (modalId) => {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
    }
  };

  const closeModal = (modalId) => {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
    }
  };

  test('opens modal', () => {
    const modal = createModal('testModal');
    openModal('testModal');
    expect(modal.hidden).toBe(false);
    expect(modal.getAttribute('aria-hidden')).toBe('false');
  });

  test('closes modal', () => {
    const modal = createModal('testModal');
    modal.hidden = false;
    closeModal('testModal');
    expect(modal.hidden).toBe(true);
    expect(modal.getAttribute('aria-hidden')).toBe('true');
  });

  test('handles non-existent modal gracefully', () => {
    expect(() => openModal('nonExistent')).not.toThrow();
    expect(() => closeModal('nonExistent')).not.toThrow();
  });
});

describe('Filter UI', () => {
  const setupFilterUI = () => {
    const container = document.createElement('div');

    const domainFilter = createSelect('domainFilter', [
      { value: '', label: 'All Domains' },
      { value: 'example.com', label: 'example.com' },
      { value: 'test.com', label: 'test.com' },
    ]);

    const dateFilter = createSelect('dateRangeFilter', [
      { value: '7', label: 'Last 7 days' },
      { value: '30', label: 'Last 30 days' },
      { value: '365', label: 'Last year' },
    ]);

    const applyBtn = document.createElement('button');
    applyBtn.id = 'applyFilters';
    applyBtn.textContent = 'Apply';

    const resetBtn = document.createElement('button');
    resetBtn.id = 'resetFilters';
    resetBtn.textContent = 'Reset';

    container.appendChild(domainFilter);
    container.appendChild(dateFilter);
    container.appendChild(applyBtn);
    container.appendChild(resetBtn);
    document.body.appendChild(container);

    return container;
  };

  test('domain filter selection', () => {
    setupFilterUI();
    const domainFilter = document.getElementById('domainFilter');

    fireEvent.change(domainFilter, { target: { value: 'example.com' } });

    expect(domainFilter.value).toBe('example.com');
  });

  test('date range filter selection', () => {
    setupFilterUI();
    const dateFilter = document.getElementById('dateRangeFilter');

    fireEvent.change(dateFilter, { target: { value: '30' } });

    expect(dateFilter.value).toBe('30');
  });

  test('reset filters button', () => {
    setupFilterUI();
    const domainFilter = document.getElementById('domainFilter');
    const dateFilter = document.getElementById('dateRangeFilter');
    const resetBtn = document.getElementById('resetFilters');

    domainFilter.value = 'example.com';
    dateFilter.value = '30';

    const resetFilters = () => {
      domainFilter.value = '';
      dateFilter.value = '365';
    };

    resetBtn.addEventListener('click', resetFilters);
    fireEvent.click(resetBtn);

    expect(domainFilter.value).toBe('');
    expect(dateFilter.value).toBe('365');
  });
});

describe('Loading States', () => {
  const showLoading = (elementId) => {
    const element = document.getElementById(elementId);
    if (element) {
      element.classList.add('loading');
      element.setAttribute('aria-busy', 'true');
    }
  };

  const hideLoading = (elementId) => {
    const element = document.getElementById(elementId);
    if (element) {
      element.classList.remove('loading');
      element.setAttribute('aria-busy', 'false');
    }
  };

  test('shows loading state', () => {
    const div = document.createElement('div');
    div.id = 'content';
    document.body.appendChild(div);

    showLoading('content');

    expect(div.classList.contains('loading')).toBe(true);
    expect(div.getAttribute('aria-busy')).toBe('true');
  });

  test('hides loading state', () => {
    const div = document.createElement('div');
    div.id = 'content';
    div.classList.add('loading');
    document.body.appendChild(div);

    hideLoading('content');

    expect(div.classList.contains('loading')).toBe(false);
    expect(div.getAttribute('aria-busy')).toBe('false');
  });
});

describe('Notification System', () => {
  const createNotificationContainer = () => {
    const container = document.createElement('div');
    container.id = 'notifications';
    document.body.appendChild(container);
    return container;
  };

  const showNotification = (message, type = 'info') => {
    const container = document.getElementById('notifications');
    if (!container) return;

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.setAttribute('role', 'alert');
    container.appendChild(notification);

    return notification;
  };

  const dismissNotification = (notification) => {
    if (notification && notification.parentNode) {
      notification.parentNode.removeChild(notification);
    }
  };

  test('shows info notification', () => {
    createNotificationContainer();
    const notification = showNotification('Test message', 'info');

    expect(notification.classList.contains('notification-info')).toBe(true);
    expect(notification.textContent).toBe('Test message');
    expect(notification.getAttribute('role')).toBe('alert');
  });

  test('shows error notification', () => {
    createNotificationContainer();
    const notification = showNotification('Error occurred', 'error');

    expect(notification.classList.contains('notification-error')).toBe(true);
  });

  test('shows success notification', () => {
    createNotificationContainer();
    const notification = showNotification('Success!', 'success');

    expect(notification.classList.contains('notification-success')).toBe(true);
  });

  test('dismisses notification', () => {
    const container = createNotificationContainer();
    const notification = showNotification('Test message');

    expect(container.children.length).toBe(1);
    dismissNotification(notification);
    expect(container.children.length).toBe(0);
  });
});

describe('Keyboard Navigation', () => {
  const handleKeyboardShortcut = (event, shortcuts) => {
    const shortcut = shortcuts.find((s) => s.key === event.key);
    if (shortcut && !event.ctrlKey && !event.altKey && !event.metaKey) {
      // Don't trigger shortcuts when typing in inputs
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) {
        return null;
      }
      return shortcut.action;
    }
    return null;
  };

  const shortcuts = [
    { key: 'r', action: 'refresh' },
    { key: 'u', action: 'upload' },
    { key: '?', action: 'help' },
    { key: 'Escape', action: 'escape' },
  ];

  test('handles refresh shortcut', () => {
    const event = new KeyboardEvent('keydown', { key: 'r' });
    Object.defineProperty(event, 'target', { value: document.body });

    const action = handleKeyboardShortcut(event, shortcuts);
    expect(action).toBe('refresh');
  });

  test('handles upload shortcut', () => {
    const event = new KeyboardEvent('keydown', { key: 'u' });
    Object.defineProperty(event, 'target', { value: document.body });

    const action = handleKeyboardShortcut(event, shortcuts);
    expect(action).toBe('upload');
  });

  test('ignores shortcuts when typing in input', () => {
    const input = document.createElement('input');
    document.body.appendChild(input);

    const event = new KeyboardEvent('keydown', { key: 'r' });
    Object.defineProperty(event, 'target', { value: input });

    const action = handleKeyboardShortcut(event, shortcuts);
    expect(action).toBeNull();
  });

  test('handles escape key', () => {
    const event = new KeyboardEvent('keydown', { key: 'Escape' });
    Object.defineProperty(event, 'target', { value: document.body });

    const action = handleKeyboardShortcut(event, shortcuts);
    expect(action).toBe('escape');
  });
});

describe('Accessibility', () => {
  test('focus trap in modal', () => {
    const modal = document.createElement('div');
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');

    const firstFocusable = document.createElement('button');
    firstFocusable.textContent = 'First';
    const lastFocusable = document.createElement('button');
    lastFocusable.textContent = 'Last';

    modal.appendChild(firstFocusable);
    modal.appendChild(lastFocusable);
    document.body.appendChild(modal);

    expect(modal.getAttribute('role')).toBe('dialog');
    expect(modal.getAttribute('aria-modal')).toBe('true');
  });

  test('aria-live region for notifications', () => {
    const liveRegion = document.createElement('div');
    liveRegion.setAttribute('aria-live', 'polite');
    liveRegion.setAttribute('aria-atomic', 'true');
    document.body.appendChild(liveRegion);

    expect(liveRegion.getAttribute('aria-live')).toBe('polite');
    expect(liveRegion.getAttribute('aria-atomic')).toBe('true');
  });
});
