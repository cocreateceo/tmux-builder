# E2E Test Run Skill

## Purpose

Execute Playwright end-to-end tests against deployed web applications, generate reports, and capture results for CI/CD integration.

## Prerequisites

- Node.js installed (v16+)
- Playwright Test installed (`npm install @playwright/test`)
- Playwright browsers installed (`npx playwright install`)
- E2E test files created in tests directory

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `test_dir` | Directory containing tests | No | `./tests/e2e/` |
| `base_url` | Override base URL | No | `https://staging.example.com` |
| `browser` | Browser to run tests | No | `chromium`, `firefox`, `webkit` |
| `reporter` | Test reporter format | No | `html`, `json`, `list` |
| `workers` | Parallel workers | No | `4` |
| `retries` | Number of retries | No | `2` |
| `grep` | Filter tests by name | No | `login` |

## Usage Examples

### Run All Tests

```bash
npx playwright test
```

### Run Tests in Specific Directory

```bash
npx playwright test {test_dir}
```

### Run Tests with Specific Browser

```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

### Run Tests Against Different URL

```bash
BASE_URL={base_url} npx playwright test
```

### Run Tests with Custom Config

```bash
npx playwright test --config=playwright.config.ts
```

### Run Specific Test File

```bash
npx playwright test tests/e2e/homepage.spec.ts
```

### Run Tests Matching Pattern

```bash
npx playwright test --grep "{grep}"
npx playwright test --grep "login|logout"
npx playwright test --grep-invert "slow"
```

### Run Tests with Retries

```bash
npx playwright test --retries={retries:-2}
```

### Run Tests in Parallel

```bash
npx playwright test --workers={workers:-4}
```

### Run Tests in Headed Mode (Debug)

```bash
npx playwright test --headed
```

### Run Tests with Trace

```bash
npx playwright test --trace on
```

### Generate HTML Report

```bash
npx playwright test --reporter=html
npx playwright show-report
```

### Generate JSON Report

```bash
npx playwright test --reporter=json > test-results.json
```

### Generate JUnit Report (CI/CD)

```bash
npx playwright test --reporter=junit > junit-results.xml
```

### Multiple Reporters

```bash
npx playwright test --reporter=list --reporter=html
```

### Full CI/CD Command

```bash
#!/bin/bash
# run-e2e-tests.sh

export BASE_URL="${BASE_URL:-{base_url}}"
export CI=true

echo "Running E2E tests against $BASE_URL"

npx playwright test \
    --project=chromium \
    --reporter=html \
    --reporter=junit \
    --retries=2 \
    --workers=2

EXIT_CODE=$?

# Generate report artifacts
npx playwright show-report --host 0.0.0.0 &

exit $EXIT_CODE
```

### Run with Debugging

```bash
# Debug mode with inspector
PWDEBUG=1 npx playwright test

# Debug specific test
PWDEBUG=1 npx playwright test -g "should login"

# Show browser console
DEBUG=pw:api npx playwright test
```

### Update Snapshots

```bash
npx playwright test --update-snapshots
```

### List Available Tests

```bash
npx playwright test --list
```

## Test Results Analysis

### Check Exit Code

```bash
npx playwright test
if [ $? -eq 0 ]; then
    echo "All tests passed"
else
    echo "Some tests failed"
fi
```

### Parse JSON Results

```bash
# Generate JSON report
npx playwright test --reporter=json > results.json

# Parse results with jq
TOTAL=$(cat results.json | jq '.stats.total')
PASSED=$(cat results.json | jq '.stats.expected')
FAILED=$(cat results.json | jq '.stats.unexpected')

echo "Total: $TOTAL, Passed: $PASSED, Failed: $FAILED"
```

### Generate Summary Report

```bash
#!/bin/bash
# test-summary.sh

RESULTS=$(npx playwright test --reporter=json 2>&1)

echo "$RESULTS" | jq -r '
    "Test Summary:",
    "-------------",
    "Total Tests: \(.stats.total)",
    "Passed: \(.stats.expected)",
    "Failed: \(.stats.unexpected)",
    "Skipped: \(.stats.skipped)",
    "Duration: \(.stats.duration / 1000)s"
'
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npx playwright test
        env:
          BASE_URL: ${{ secrets.BASE_URL }}
      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
```

### GitLab CI

```yaml
# .gitlab-ci.yml
e2e-tests:
  image: mcr.microsoft.com/playwright:v1.40.0-jammy
  script:
    - npm ci
    - npx playwright test
  artifacts:
    when: always
    paths:
      - playwright-report/
    expire_in: 1 week
```

## Verification

Verify test execution results:

```bash
# Check test results exist
ls -la playwright-report/

# View HTML report
npx playwright show-report

# Check for failures in output
npx playwright test 2>&1 | grep -E "passed|failed|skipped"
```

### Verify Against Expected Results

```bash
#!/bin/bash
EXPECTED_TESTS=10
RESULTS=$(npx playwright test --reporter=json 2>&1)
ACTUAL_TESTS=$(echo "$RESULTS" | jq '.stats.total')

if [ "$ACTUAL_TESTS" -ge "$EXPECTED_TESTS" ]; then
    echo "PASS: Found $ACTUAL_TESTS tests (expected >= $EXPECTED_TESTS)"
else
    echo "FAIL: Found only $ACTUAL_TESTS tests (expected >= $EXPECTED_TESTS)"
    exit 1
fi
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Browser not found` | Browsers not installed | Run `npx playwright install` |
| `Timeout exceeded` | Tests too slow | Increase timeout in config |
| `Navigation failed` | URL not reachable | Verify BASE_URL is accessible |
| `No tests found` | Wrong test directory | Check testDir in config |
| `Worker crashed` | Memory issues | Reduce workers or fix memory leaks |

## Notes

- Run tests in CI with `CI=true` environment variable
- Use `--headed` for debugging locally
- Generate HTML reports for detailed failure analysis
- Use sharding for parallel execution across machines
- Configure retries for flaky tests
- Capture traces and screenshots on failure
- Use tags to organize and filter tests
- Consider running tests against preview deployments
