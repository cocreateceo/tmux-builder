# E2E Test Generation Skill

## Purpose

Generate end-to-end (E2E) test files using Playwright for automated browser testing of web applications, covering user flows and critical paths.

## Prerequisites

- Node.js installed (v16+)
- Playwright Test installed (`npm install @playwright/test`)
- Playwright browsers installed (`npx playwright install`)
- Understanding of application user flows

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `base_url` | Application base URL | Yes | `https://example.com` |
| `test_name` | Name of the test file | Yes | `homepage.spec.ts` |
| `output_dir` | Directory for test files | No | `./tests/e2e/` |
| `scenarios` | Test scenarios to cover | Yes | (see examples) |

## Usage Examples

### Initialize Playwright Test Project

```bash
npm init playwright@latest

# Or add to existing project
npm install -D @playwright/test
npx playwright install
```

### Basic Test File Template

```typescript
// tests/e2e/{test_name}
import { test, expect } from '@playwright/test';

test.describe('Homepage Tests', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('{base_url}');
    });

    test('should load homepage successfully', async ({ page }) => {
        await expect(page).toHaveTitle(/Expected Title/);
        await expect(page.locator('h1')).toBeVisible();
    });

    test('should have working navigation', async ({ page }) => {
        await page.click('nav a[href="/about"]');
        await expect(page).toHaveURL(/.*about/);
    });
});
```

### Generate Authentication Test

```typescript
// tests/e2e/auth.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
    test('should allow user to login', async ({ page }) => {
        await page.goto('{base_url}/login');

        // Fill login form
        await page.fill('input[name="email"]', 'test@example.com');
        await page.fill('input[name="password"]', 'password123');
        await page.click('button[type="submit"]');

        // Verify successful login
        await expect(page).toHaveURL(/.*dashboard/);
        await expect(page.locator('.user-welcome')).toContainText('Welcome');
    });

    test('should show error for invalid credentials', async ({ page }) => {
        await page.goto('{base_url}/login');

        await page.fill('input[name="email"]', 'wrong@example.com');
        await page.fill('input[name="password"]', 'wrongpassword');
        await page.click('button[type="submit"]');

        await expect(page.locator('.error-message')).toBeVisible();
        await expect(page.locator('.error-message')).toContainText('Invalid');
    });

    test('should allow user to logout', async ({ page }) => {
        // Login first
        await page.goto('{base_url}/login');
        await page.fill('input[name="email"]', 'test@example.com');
        await page.fill('input[name="password"]', 'password123');
        await page.click('button[type="submit"]');

        // Logout
        await page.click('button.logout');

        await expect(page).toHaveURL(/.*login/);
    });
});
```

### Generate Form Test

```typescript
// tests/e2e/contact-form.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Contact Form', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('{base_url}/contact');
    });

    test('should submit form successfully', async ({ page }) => {
        await page.fill('input[name="name"]', 'John Doe');
        await page.fill('input[name="email"]', 'john@example.com');
        await page.fill('textarea[name="message"]', 'Test message content');

        await page.click('button[type="submit"]');

        await expect(page.locator('.success-message')).toBeVisible();
        await expect(page.locator('.success-message')).toContainText('Thank you');
    });

    test('should validate required fields', async ({ page }) => {
        await page.click('button[type="submit"]');

        await expect(page.locator('input[name="name"]:invalid')).toBeVisible();
        await expect(page.locator('input[name="email"]:invalid')).toBeVisible();
    });

    test('should validate email format', async ({ page }) => {
        await page.fill('input[name="name"]', 'John Doe');
        await page.fill('input[name="email"]', 'invalid-email');
        await page.fill('textarea[name="message"]', 'Test message');

        await page.click('button[type="submit"]');

        await expect(page.locator('.error-message')).toContainText('valid email');
    });
});
```

### Generate Navigation Test

```typescript
// tests/e2e/navigation.spec.ts
import { test, expect } from '@playwright/test';

const pages = [
    { path: '/', title: 'Home' },
    { path: '/about', title: 'About' },
    { path: '/services', title: 'Services' },
    { path: '/contact', title: 'Contact' }
];

test.describe('Site Navigation', () => {
    for (const pageInfo of pages) {
        test(`should load ${pageInfo.title} page`, async ({ page }) => {
            await page.goto(`{base_url}${pageInfo.path}`);
            await expect(page).toHaveTitle(new RegExp(pageInfo.title, 'i'));
        });
    }

    test('should have consistent header on all pages', async ({ page }) => {
        for (const pageInfo of pages) {
            await page.goto(`{base_url}${pageInfo.path}`);
            await expect(page.locator('header')).toBeVisible();
            await expect(page.locator('nav')).toBeVisible();
        }
    });

    test('should have consistent footer on all pages', async ({ page }) => {
        for (const pageInfo of pages) {
            await page.goto(`{base_url}${pageInfo.path}`);
            await expect(page.locator('footer')).toBeVisible();
        }
    });
});
```

### Generate API Integration Test

```typescript
// tests/e2e/api-integration.spec.ts
import { test, expect } from '@playwright/test';

test.describe('API Integration', () => {
    test('should display data from API', async ({ page }) => {
        await page.goto('{base_url}/products');

        // Wait for API data to load
        await page.waitForResponse(response =>
            response.url().includes('/api/products') &&
            response.status() === 200
        );

        // Verify data is displayed
        await expect(page.locator('.product-card')).toHaveCount(10);
    });

    test('should handle API errors gracefully', async ({ page }) => {
        // Mock API error
        await page.route('**/api/products', route => {
            route.fulfill({
                status: 500,
                body: JSON.stringify({ error: 'Internal server error' })
            });
        });

        await page.goto('{base_url}/products');

        await expect(page.locator('.error-state')).toBeVisible();
    });
});
```

### Generate Responsive Test

```typescript
// tests/e2e/responsive.spec.ts
import { test, expect, devices } from '@playwright/test';

const viewports = [
    { name: 'Desktop', width: 1920, height: 1080 },
    { name: 'Tablet', width: 768, height: 1024 },
    { name: 'Mobile', width: 375, height: 812 }
];

test.describe('Responsive Design', () => {
    for (const viewport of viewports) {
        test(`should display correctly on ${viewport.name}`, async ({ page }) => {
            await page.setViewportSize({
                width: viewport.width,
                height: viewport.height
            });

            await page.goto('{base_url}');

            // Core content should be visible
            await expect(page.locator('main')).toBeVisible();
            await expect(page.locator('h1')).toBeVisible();
        });
    }

    test('mobile menu should toggle', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 812 });
        await page.goto('{base_url}');

        // Menu should be hidden initially
        await expect(page.locator('nav.mobile-menu')).toBeHidden();

        // Toggle menu
        await page.click('button.menu-toggle');
        await expect(page.locator('nav.mobile-menu')).toBeVisible();
    });
});
```

### Playwright Config File

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
    testDir: './tests/e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: 'html',
    use: {
        baseURL: '{base_url}',
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
        {
            name: 'firefox',
            use: { ...devices['Desktop Firefox'] },
        },
        {
            name: 'webkit',
            use: { ...devices['Desktop Safari'] },
        },
    ],
});
```

## Verification

Verify test files were generated correctly:

```bash
# Check test file exists
ls -la tests/e2e/{test_name}

# Validate TypeScript syntax
npx tsc --noEmit tests/e2e/{test_name}

# Run tests to verify
npx playwright test tests/e2e/{test_name} --reporter=list
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Selector not found` | Wrong selector | Inspect page and update selector |
| `Timeout exceeded` | Slow page load | Increase timeout or add waitFor |
| `Navigation interrupted` | Page redirects | Handle redirects in test |
| `TypeScript error` | Invalid syntax | Fix TypeScript errors |
| `Test flaky` | Race conditions | Add proper waits and assertions |

## Notes

- Use data-testid attributes for stable selectors
- Keep tests independent (no shared state between tests)
- Use page object model for maintainability
- Run tests in CI/CD pipeline
- Use visual comparison for UI regression testing
- Mock external APIs for reliable tests
- Generate tests based on user stories
- Cover happy paths first, then edge cases
