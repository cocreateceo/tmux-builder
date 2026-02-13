# Responsive Check Skill

## Purpose

Verify that deployed websites display correctly across all device sizes - mobile, tablet, and desktop. Catch layout issues, overflow problems, and touch target sizes before users do.

## Prerequisites

- Node.js installed (v16+)
- Playwright installed (`npm install playwright`)
- Playwright browsers installed (`npx playwright install chromium`)
- Target URL accessible

## Viewport Definitions

| Device | Width | Height | Category |
|--------|-------|--------|----------|
| Mobile S | 320px | 568px | Mobile |
| Mobile M | 375px | 667px | Mobile |
| Mobile L | 414px | 896px | Mobile |
| Tablet | 768px | 1024px | Tablet |
| Laptop | 1024px | 768px | Desktop |
| Desktop | 1440px | 900px | Desktop |
| Large Desktop | 1920px | 1080px | Desktop |

## Responsive Test Script

### Complete Test Script (Node.js)

```javascript
// responsive-check.js
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const URL = process.argv[2] || '{url}';
const OUTPUT_DIR = process.argv[3] || './responsive-test';

const viewports = [
    { name: 'mobile-s', width: 320, height: 568, category: 'mobile' },
    { name: 'mobile-m', width: 375, height: 667, category: 'mobile' },
    { name: 'mobile-l', width: 414, height: 896, category: 'mobile' },
    { name: 'tablet', width: 768, height: 1024, category: 'tablet' },
    { name: 'laptop', width: 1024, height: 768, category: 'desktop' },
    { name: 'desktop', width: 1440, height: 900, category: 'desktop' },
    { name: 'desktop-xl', width: 1920, height: 1080, category: 'desktop' }
];

async function runResponsiveTests() {
    const results = {
        url: URL,
        timestamp: new Date().toISOString(),
        passed: true,
        viewports: []
    };

    // Ensure output directory exists
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });

    const browser = await chromium.launch();

    for (const viewport of viewports) {
        console.log(`Testing ${viewport.name} (${viewport.width}x${viewport.height})...`);

        const context = await browser.newContext({
            viewport: { width: viewport.width, height: viewport.height },
            deviceScaleFactor: viewport.category === 'mobile' ? 2 : 1,
            isMobile: viewport.category === 'mobile',
            hasTouch: viewport.category !== 'desktop'
        });

        const page = await context.newPage();
        const viewportResult = {
            name: viewport.name,
            width: viewport.width,
            height: viewport.height,
            category: viewport.category,
            passed: true,
            issues: [],
            screenshot: `${viewport.name}.png`
        };

        try {
            await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
            await page.waitForTimeout(1000);

            // Check for horizontal overflow
            const hasHorizontalOverflow = await page.evaluate(() => {
                return document.documentElement.scrollWidth > document.documentElement.clientWidth;
            });

            if (hasHorizontalOverflow) {
                viewportResult.issues.push('Horizontal overflow detected - content wider than viewport');
                viewportResult.passed = false;
            }

            // Check for tiny text (less than 12px)
            const hasTinyText = await page.evaluate(() => {
                const elements = document.querySelectorAll('p, span, a, li, td, th, label');
                for (const el of elements) {
                    const fontSize = parseFloat(window.getComputedStyle(el).fontSize);
                    if (fontSize < 12 && el.textContent.trim().length > 0) {
                        return true;
                    }
                }
                return false;
            });

            if (hasTinyText) {
                viewportResult.issues.push('Text smaller than 12px detected - may be hard to read');
            }

            // Check for touch target sizes on mobile
            if (viewport.category === 'mobile') {
                const smallTouchTargets = await page.evaluate(() => {
                    const clickables = document.querySelectorAll('a, button, input, select, textarea, [onclick]');
                    const small = [];
                    for (const el of clickables) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            if (rect.width < 44 || rect.height < 44) {
                                small.push({
                                    tag: el.tagName,
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height)
                                });
                            }
                        }
                    }
                    return small.slice(0, 5); // Return first 5
                });

                if (smallTouchTargets.length > 0) {
                    viewportResult.issues.push(
                        `Touch targets too small (<44px): ${smallTouchTargets.map(t =>
                            `${t.tag}(${t.width}x${t.height})`).join(', ')}`
                    );
                }
            }

            // Check for images that might be too large
            const oversizedImages = await page.evaluate(() => {
                const images = document.querySelectorAll('img');
                const oversized = [];
                for (const img of images) {
                    if (img.naturalWidth > 2000 || img.naturalHeight > 2000) {
                        oversized.push({
                            src: img.src.substring(0, 50),
                            natural: `${img.naturalWidth}x${img.naturalHeight}`
                        });
                    }
                }
                return oversized;
            });

            if (oversizedImages.length > 0) {
                viewportResult.issues.push(
                    `Large images may slow mobile: ${oversizedImages.length} images > 2000px`
                );
            }

            // Check for fixed positioning issues
            const fixedElements = await page.evaluate(() => {
                const fixed = document.querySelectorAll('*');
                let count = 0;
                for (const el of fixed) {
                    if (window.getComputedStyle(el).position === 'fixed') {
                        count++;
                    }
                }
                return count;
            });

            if (fixedElements > 3) {
                viewportResult.issues.push(
                    `${fixedElements} fixed position elements - may cause mobile issues`
                );
            }

            // Take screenshot
            await page.screenshot({
                path: path.join(OUTPUT_DIR, viewportResult.screenshot),
                fullPage: false
            });

        } catch (error) {
            viewportResult.passed = false;
            viewportResult.issues.push(`Error: ${error.message}`);
        }

        if (!viewportResult.passed || viewportResult.issues.length > 0) {
            results.passed = false;
        }

        results.viewports.push(viewportResult);
        await context.close();
    }

    await browser.close();

    // Save results
    const reportPath = path.join(OUTPUT_DIR, 'responsive-report.json');
    fs.writeFileSync(reportPath, JSON.stringify(results, null, 2));

    // Print summary
    console.log('\n=== RESPONSIVE TEST RESULTS ===\n');
    console.log(`URL: ${URL}`);
    console.log(`Overall: ${results.passed ? 'PASS' : 'FAIL'}\n`);

    for (const vp of results.viewports) {
        const status = vp.issues.length === 0 ? 'PASS' : 'WARN';
        console.log(`${status}: ${vp.name} (${vp.width}x${vp.height})`);
        for (const issue of vp.issues) {
            console.log(`  - ${issue}`);
        }
    }

    console.log(`\nScreenshots saved to: ${OUTPUT_DIR}/`);
    console.log(`Full report: ${reportPath}`);

    return results;
}

runResponsiveTests().catch(console.error);
```

### Quick Bash Wrapper

```bash
#!/bin/bash
# responsive-check.sh

URL="${1:-https://example.com}"
OUTPUT_DIR="${2:-./responsive-test}"

echo "Running responsive tests for: $URL"
echo "Output directory: $OUTPUT_DIR"

node responsive-check.js "$URL" "$OUTPUT_DIR"

if [ $? -eq 0 ]; then
    echo ""
    echo "PASS: Responsive tests completed"
    exit 0
else
    echo ""
    echo "FAIL: Responsive tests found issues"
    exit 1
fi
```

## Common Responsive Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Horizontal scroll | Fixed width elements | Use max-width, percentages, or vw units |
| Text too small | No mobile font scaling | Use clamp() or media queries |
| Touch targets too small | Buttons/links < 44px | Min 44x44px for touch elements |
| Images overflow | Fixed image dimensions | Use max-width: 100% |
| Nav menu broken | Desktop nav on mobile | Add hamburger menu for mobile |
| Content hidden | overflow: hidden issues | Check parent containers |

## CSS Quick Fixes

```css
/* Prevent horizontal overflow */
html, body {
  overflow-x: hidden;
}

/* Responsive images */
img {
  max-width: 100%;
  height: auto;
}

/* Minimum touch targets */
button, a, input, select {
  min-height: 44px;
  min-width: 44px;
}

/* Responsive font sizing */
html {
  font-size: clamp(14px, 2.5vw, 18px);
}

/* Container that doesn't overflow */
.container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1rem;
}
```

## Verification Steps

1. Run responsive test script
2. Review screenshots for visual issues
3. Check report for automated warnings
4. Manually test on real device if possible
5. Fix any issues found
6. Re-run tests to confirm fixes

## Integration

Use this skill:
- After frontend code is generated
- Before deployment
- After any CSS/layout changes
- As part of CI/CD pipeline

The test results should be included in deployment verification.
