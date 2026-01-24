# Screenshot Capture Skill

## Purpose

Capture screenshots of deployed web pages using Playwright for visual verification, documentation, and automated testing.

## Prerequisites

- Node.js installed (v16+)
- Playwright installed (`npm install playwright`)
- Playwright browsers installed (`npx playwright install chromium`)
- Target URL accessible from execution environment

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `url` | Target URL to capture | Yes | `https://example.com` |
| `output_path` | Path to save screenshot | Yes | `./screenshots/home.png` |
| `viewport_width` | Browser viewport width | No | `1920` |
| `viewport_height` | Browser viewport height | No | `1080` |
| `full_page` | Capture full page scroll | No | `true` |
| `wait_for` | Selector to wait for | No | `#content` |
| `delay` | Delay before capture (ms) | No | `1000` |

## Usage Examples

### Install Playwright

```bash
npm init -y
npm install playwright
npx playwright install chromium
```

### Basic Screenshot (Node.js)

```javascript
// screenshot.js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();

    await page.goto('{url}');
    await page.screenshot({ path: '{output_path}' });

    await browser.close();
    console.log('Screenshot saved to {output_path}');
})();
```

Run with:
```bash
node screenshot.js
```

### Full Page Screenshot

```javascript
// screenshot-full.js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();

    await page.setViewportSize({
        width: {viewport_width:-1920},
        height: {viewport_height:-1080}
    });

    await page.goto('{url}');
    await page.screenshot({
        path: '{output_path}',
        fullPage: true
    });

    await browser.close();
    console.log('Full page screenshot saved');
})();
```

### Screenshot with Wait and Delay

```javascript
// screenshot-wait.js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();

    await page.goto('{url}', { waitUntil: 'networkidle' });

    // Wait for specific element
    await page.waitForSelector('{wait_for:-body}');

    // Additional delay for animations
    await page.waitForTimeout({delay:-1000});

    await page.screenshot({ path: '{output_path}' });

    await browser.close();
    console.log('Screenshot captured');
})();
```

### Multiple Viewport Screenshots

```javascript
// screenshot-responsive.js
const { chromium } = require('playwright');

const viewports = [
    { name: 'desktop', width: 1920, height: 1080 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'mobile', width: 375, height: 812 }
];

(async () => {
    const browser = await chromium.launch();

    for (const viewport of viewports) {
        const page = await browser.newPage();
        await page.setViewportSize({
            width: viewport.width,
            height: viewport.height
        });

        await page.goto('{url}');
        await page.screenshot({
            path: `./screenshots/${viewport.name}.png`
        });

        console.log(`Captured ${viewport.name} screenshot`);
        await page.close();
    }

    await browser.close();
})();
```

### Screenshot with Authentication

```javascript
// screenshot-auth.js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const context = await browser.newContext({
        httpCredentials: {
            username: '{username}',
            password: '{password}'
        }
    });

    const page = await context.newPage();
    await page.goto('{url}');
    await page.screenshot({ path: '{output_path}' });

    await browser.close();
})();
```

### Element Screenshot

```javascript
// screenshot-element.js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();

    await page.goto('{url}');

    // Screenshot specific element
    const element = await page.locator('{selector}');
    await element.screenshot({ path: '{output_path}' });

    await browser.close();
})();
```

### Screenshot with Dark Mode

```javascript
// screenshot-dark.js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const context = await browser.newContext({
        colorScheme: 'dark'
    });

    const page = await context.newPage();
    await page.goto('{url}');
    await page.screenshot({ path: '{output_path}' });

    await browser.close();
})();
```

### Bash Wrapper Script

```bash
#!/bin/bash
# screenshot.sh

URL="${1:-{url}}"
OUTPUT="${2:-./screenshots/screenshot.png}"

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT")"

# Run Playwright screenshot
node -e "
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('$URL', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: '$OUTPUT', fullPage: true });
    await browser.close();
    console.log('Screenshot saved to $OUTPUT');
})();
"

if [ $? -eq 0 ]; then
    echo "PASS: Screenshot captured successfully"
    exit 0
else
    echo "FAIL: Screenshot capture failed"
    exit 1
fi
```

### Python Alternative (Playwright-Python)

```python
#!/usr/bin/env python3
# screenshot.py
from playwright.sync_api import sync_playwright
import sys

url = "{url}"
output_path = "{output_path}"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(url, wait_until="networkidle")
    page.screenshot(path=output_path, full_page=True)
    browser.close()
    print(f"Screenshot saved to {output_path}")
```

Install with:
```bash
pip install playwright
playwright install chromium
```

## Verification

Verify screenshot was captured:

```bash
# Check file exists and has content
if [ -f "{output_path}" ] && [ -s "{output_path}" ]; then
    echo "PASS: Screenshot file created"
    ls -lh "{output_path}"
else
    echo "FAIL: Screenshot file not found or empty"
fi

# Check image dimensions (requires imagemagick)
identify "{output_path}"
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Browser not installed` | Playwright browsers missing | Run `npx playwright install` |
| `Navigation timeout` | Page load too slow | Increase timeout or check URL |
| `Protocol error` | Browser crashed | Increase memory, check for loops |
| `File permission denied` | Cannot write to path | Check directory permissions |
| `Element not found` | Selector doesn't match | Verify selector or wait for element |

## Notes

- Use `networkidle` wait for pages with dynamic content
- Full page screenshots can be very large for long pages
- Consider PNG for quality, JPEG for smaller file size
- Add delays for pages with animations
- Use headless mode for server environments (default)
- Set `headless: false` for debugging
- Consider using Percy or Chromatic for visual regression testing
- Screenshots are useful for deployment verification and documentation
