# DMARC Dashboard - E2E Tests

End-to-end tests for the DMARC Dashboard using Playwright.

## Prerequisites

- Node.js 18+
- Docker (for running the application)

## Setup

```bash
cd tests/e2e
npm install
npx playwright install
```

## Running Tests

### All Tests
```bash
npm test
```

### With UI
```bash
npm run test:ui
```

### Headed Mode (visible browser)
```bash
npm run test:headed
```

### Specific Browser
```bash
npm run test:chromium
npm run test:firefox
npm run test:webkit
```

### Mobile Tests Only
```bash
npm run test:mobile
```

### Debug Mode
```bash
npm run test:debug
```

## Test Structure

```
tests/e2e/
├── playwright.config.ts  # Playwright configuration
├── package.json          # Dependencies and scripts
├── tests/
│   ├── dashboard.spec.ts # Main dashboard tests
│   ├── mobile.spec.ts    # Mobile responsiveness tests
│   └── api.spec.ts       # API endpoint tests
└── README.md
```

## Test Coverage

### Dashboard Tests (`dashboard.spec.ts`)
- Page loading and title
- Stats cards display
- Charts rendering
- Reports table
- Filter controls
- Dark mode toggle
- Help modal
- Upload modal
- Export dropdown

### Mobile Tests (`mobile.spec.ts`)
- Mobile-friendly header layout
- Responsive grid layouts
- Touch-friendly button sizes
- Modal display on mobile
- Tablet responsiveness

### API Tests (`api.spec.ts`)
- Health check endpoint
- Dashboard data endpoints
- Filtering functionality
- Error handling

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8000` | Target URL for tests |
| `CI` | - | Set in CI environments |

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run E2E Tests
  run: |
    cd tests/e2e
    npm ci
    npx playwright install --with-deps
    npm test
  env:
    BASE_URL: http://localhost:8000
```

## Viewing Test Reports

After running tests, view the HTML report:

```bash
npm run report
```

Reports are saved to `playwright-report/`.

## Debugging Failed Tests

1. Use debug mode: `npm run test:debug`
2. View trace files in the report
3. Check screenshots in `test-results/`

## Writing New Tests

```typescript
import { test, expect } from '@playwright/test';

test('should do something', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('selector')).toBeVisible();
});
```

## Best Practices

1. Use `data-testid` attributes for stable selectors
2. Avoid `page.waitForTimeout()` - use explicit waits
3. Test user journeys, not implementation details
4. Keep tests independent and isolated
5. Use page objects for complex pages
