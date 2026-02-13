# Asset Verification Skill

## Purpose

Verify that all static assets (images, fonts, CSS, JavaScript) load correctly on deployed websites. Catch broken links, missing files, and slow-loading resources before users encounter them.

## Why Asset Verification Matters

Common deployment issues:
- Images show broken placeholders
- Fonts fall back to system fonts
- CSS/JS files 404 causing broken layouts
- Assets load slowly (not optimized/cached)
- Mixed content warnings (HTTP on HTTPS site)

## Prerequisites

- Node.js installed (v16+)
- Playwright installed
- `curl` for direct asset checks
- Target URL accessible

## Asset Verification Script

### Complete Asset Check (Node.js)

```javascript
// asset-verification.js
const { chromium } = require('playwright');
const fs = require('fs');

const URL = process.argv[2] || '{url}';
const OUTPUT_FILE = process.argv[3] || 'asset-report.json';

async function verifyAssets() {
    const results = {
        url: URL,
        timestamp: new Date().toISOString(),
        passed: true,
        summary: {
            total: 0,
            loaded: 0,
            failed: 0,
            slow: 0
        },
        assets: {
            images: [],
            stylesheets: [],
            scripts: [],
            fonts: [],
            other: []
        },
        issues: []
    };

    const browser = await chromium.launch();
    const context = await browser.newContext();
    const page = await context.newPage();

    // Track all network requests
    const requests = new Map();

    page.on('request', request => {
        requests.set(request.url(), {
            url: request.url(),
            type: request.resourceType(),
            startTime: Date.now()
        });
    });

    page.on('response', response => {
        const req = requests.get(response.url());
        if (req) {
            req.status = response.status();
            req.endTime = Date.now();
            req.duration = req.endTime - req.startTime;
            req.ok = response.ok();
        }
    });

    page.on('requestfailed', request => {
        const req = requests.get(request.url());
        if (req) {
            req.failed = true;
            req.error = request.failure()?.errorText || 'Unknown error';
        }
    });

    try {
        console.log(`Loading: ${URL}`);
        await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
        await page.waitForTimeout(2000); // Extra time for lazy-loaded assets

        // Process collected requests
        for (const [url, req] of requests) {
            results.summary.total++;

            const asset = {
                url: url.length > 100 ? url.substring(0, 100) + '...' : url,
                fullUrl: url,
                status: req.status || 0,
                duration: req.duration || 0,
                ok: req.ok !== false && !req.failed
            };

            if (req.failed) {
                asset.error = req.error;
                asset.ok = false;
            }

            // Categorize
            const type = req.type;
            if (type === 'image') {
                results.assets.images.push(asset);
            } else if (type === 'stylesheet') {
                results.assets.stylesheets.push(asset);
            } else if (type === 'script') {
                results.assets.scripts.push(asset);
            } else if (type === 'font') {
                results.assets.fonts.push(asset);
            } else if (['document', 'xhr', 'fetch'].includes(type)) {
                // Skip document and API calls
                results.summary.total--;
                continue;
            } else {
                results.assets.other.push(asset);
            }

            // Track success/failure
            if (asset.ok) {
                results.summary.loaded++;
            } else {
                results.summary.failed++;
                results.issues.push(`FAILED: ${type} - ${asset.url} (${asset.error || asset.status})`);
                results.passed = false;
            }

            // Track slow assets (> 3 seconds)
            if (asset.duration > 3000) {
                results.summary.slow++;
                results.issues.push(`SLOW: ${type} - ${asset.url} (${asset.duration}ms)`);
            }
        }

        // Check for broken images in DOM
        const brokenImages = await page.evaluate(() => {
            const images = document.querySelectorAll('img');
            const broken = [];
            for (const img of images) {
                if (!img.complete || img.naturalWidth === 0) {
                    broken.push(img.src || img.dataset.src || 'unknown');
                }
            }
            return broken;
        });

        for (const src of brokenImages) {
            if (!results.issues.some(i => i.includes(src))) {
                results.issues.push(`BROKEN IMAGE: ${src}`);
                results.passed = false;
            }
        }

        // Check for missing fonts (fallback detection)
        const fontIssues = await page.evaluate(() => {
            const issues = [];
            const testString = 'mmmmmmmmmmlli';
            const defaultWidth = {};

            // Get default widths for common fallbacks
            const span = document.createElement('span');
            span.style.position = 'absolute';
            span.style.visibility = 'hidden';
            span.style.fontSize = '72px';
            span.textContent = testString;
            document.body.appendChild(span);

            for (const fallback of ['serif', 'sans-serif', 'monospace']) {
                span.style.fontFamily = fallback;
                defaultWidth[fallback] = span.offsetWidth;
            }

            // Check custom fonts
            const elements = document.querySelectorAll('*');
            const checkedFonts = new Set();

            for (const el of elements) {
                const fontFamily = window.getComputedStyle(el).fontFamily;
                const fonts = fontFamily.split(',').map(f => f.trim().replace(/['"]/g, ''));
                const primaryFont = fonts[0];

                if (primaryFont && !checkedFonts.has(primaryFont) &&
                    !['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy'].includes(primaryFont.toLowerCase())) {
                    checkedFonts.add(primaryFont);

                    span.style.fontFamily = fontFamily;
                    const currentWidth = span.offsetWidth;

                    // If width matches a fallback exactly, font probably didn't load
                    if (Object.values(defaultWidth).includes(currentWidth)) {
                        issues.push(primaryFont);
                    }
                }
            }

            span.remove();
            return [...new Set(issues)];
        });

        for (const font of fontIssues) {
            results.issues.push(`FONT MAY NOT BE LOADED: ${font}`);
        }

        // Check for mixed content
        const mixedContent = await page.evaluate(() => {
            if (location.protocol !== 'https:') return [];
            const mixed = [];
            document.querySelectorAll('[src], [href]').forEach(el => {
                const url = el.src || el.href;
                if (url && url.startsWith('http:')) {
                    mixed.push(url);
                }
            });
            return mixed;
        });

        for (const url of mixedContent) {
            results.issues.push(`MIXED CONTENT: ${url}`);
            results.passed = false;
        }

    } catch (error) {
        results.passed = false;
        results.issues.push(`ERROR: ${error.message}`);
    }

    await browser.close();

    // Save report
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(results, null, 2));

    // Print summary
    console.log('\n=== ASSET VERIFICATION RESULTS ===\n');
    console.log(`URL: ${URL}`);
    console.log(`Total Assets: ${results.summary.total}`);
    console.log(`Loaded: ${results.summary.loaded}`);
    console.log(`Failed: ${results.summary.failed}`);
    console.log(`Slow (>3s): ${results.summary.slow}`);
    console.log(`\nOverall: ${results.passed ? 'PASS' : 'FAIL'}`);

    if (results.issues.length > 0) {
        console.log('\nIssues Found:');
        for (const issue of results.issues) {
            console.log(`  - ${issue}`);
        }
    }

    console.log(`\nFull report: ${OUTPUT_FILE}`);

    return results;
}

verifyAssets().catch(console.error);
```

### Quick Bash Asset Check

```bash
#!/bin/bash
# quick-asset-check.sh

URL="${1:-https://example.com}"

echo "=== Quick Asset Check: $URL ==="
echo ""

# Get the page and extract asset URLs
ASSETS=$(curl -s "$URL" | grep -oE '(src|href)="[^"]*\.(js|css|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)"' | \
    sed 's/.*="\([^"]*\)"/\1/' | sort -u)

FAILED=0
TOTAL=0

for ASSET in $ASSETS; do
    TOTAL=$((TOTAL + 1))

    # Handle relative URLs
    if [[ "$ASSET" == /* ]]; then
        FULL_URL="${URL%/}$ASSET"
    elif [[ "$ASSET" != http* ]]; then
        FULL_URL="${URL%/}/$ASSET"
    else
        FULL_URL="$ASSET"
    fi

    # Check if asset loads
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FULL_URL")

    if [ "$STATUS" -eq 200 ]; then
        echo "OK: $ASSET"
    else
        echo "FAIL ($STATUS): $ASSET"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "=== Summary ==="
echo "Total: $TOTAL"
echo "Failed: $FAILED"

if [ $FAILED -gt 0 ]; then
    exit 1
fi
```

## Verification Checklist

### Images
- [ ] All images load (no broken placeholders)
- [ ] Images have appropriate sizes (not oversized)
- [ ] Alt text present for accessibility
- [ ] Lazy loading works for below-fold images

### Stylesheets
- [ ] All CSS files load (HTTP 200)
- [ ] No 404 errors in CSS (missing fonts, images)
- [ ] Critical CSS loads first

### Scripts
- [ ] All JS files load
- [ ] No console errors from missing scripts
- [ ] Scripts execute without errors

### Fonts
- [ ] Custom fonts load (not falling back)
- [ ] Font files accessible (CORS if CDN)
- [ ] Font display strategy set (swap recommended)

### General
- [ ] No mixed content (HTTP on HTTPS)
- [ ] Assets load in reasonable time (<3s)
- [ ] CDN/caching headers present
- [ ] Compression enabled (gzip/brotli)

## Common Issues and Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Image 404 | Wrong path | Check src path, case sensitivity |
| Font not loading | CORS blocked | Add CORS headers to font server |
| CSS broken | Missing imports | Check @import paths |
| JS errors | Missing dependencies | Check script load order |
| Mixed content | HTTP asset on HTTPS | Update URLs to HTTPS or // |
| Slow loading | Large files | Compress, use CDN, lazy load |

## Integration

Run asset verification:
- After deployment
- After content updates
- As part of health check suite
- In CI/CD pipeline before going live
