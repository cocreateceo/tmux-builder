# Health Check Skill

## Purpose

Perform HTTP health checks on deployed web applications to verify availability, response codes, and basic functionality.

## Prerequisites

- `curl` or `httpie` installed for HTTP requests
- Target URL accessible from execution environment
- (Optional) `jq` for JSON response parsing

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `url` | Target URL to check | Yes | `https://example.com` |
| `expected_status` | Expected HTTP status code | No | `200` |
| `timeout` | Request timeout in seconds | No | `30` |
| `retries` | Number of retry attempts | No | `3` |
| `headers` | Custom headers to send | No | `Authorization: Bearer token` |

## Usage Examples

### Basic Health Check

```bash
curl -s -o /dev/null -w "%{http_code}" {url}
```

### Health Check with Status Verification

```bash
#!/bin/bash
URL="{url}"
EXPECTED_STATUS="${expected_status:-200}"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL")

if [ "$STATUS" -eq "$EXPECTED_STATUS" ]; then
    echo "PASS: $URL returned $STATUS"
    exit 0
else
    echo "FAIL: $URL returned $STATUS (expected $EXPECTED_STATUS)"
    exit 1
fi
```

### Health Check with Timeout and Retries

```bash
#!/bin/bash
URL="{url}"
TIMEOUT="${timeout:-30}"
RETRIES="${retries:-3}"
EXPECTED_STATUS="${expected_status:-200}"

for i in $(seq 1 $RETRIES); do
    echo "Attempt $i of $RETRIES..."
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$URL")

    if [ "$STATUS" -eq "$EXPECTED_STATUS" ]; then
        echo "PASS: $URL returned $STATUS"
        exit 0
    fi

    echo "Got $STATUS, retrying in 5 seconds..."
    sleep 5
done

echo "FAIL: $URL did not return $EXPECTED_STATUS after $RETRIES attempts"
exit 1
```

### Health Check with Response Time

```bash
#!/bin/bash
URL="{url}"

RESULT=$(curl -s -o /dev/null -w "%{http_code}|%{time_total}|%{time_connect}|%{time_starttransfer}" "$URL")

HTTP_CODE=$(echo $RESULT | cut -d'|' -f1)
TIME_TOTAL=$(echo $RESULT | cut -d'|' -f2)
TIME_CONNECT=$(echo $RESULT | cut -d'|' -f3)
TIME_TTFB=$(echo $RESULT | cut -d'|' -f4)

echo "URL: $URL"
echo "Status: $HTTP_CODE"
echo "Total Time: ${TIME_TOTAL}s"
echo "Connect Time: ${TIME_CONNECT}s"
echo "Time to First Byte: ${TIME_TTFB}s"

if [ "$HTTP_CODE" -eq 200 ]; then
    exit 0
else
    exit 1
fi
```

### Health Check with Content Verification

```bash
#!/bin/bash
URL="{url}"
EXPECTED_CONTENT="Welcome"

RESPONSE=$(curl -s "$URL")
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL")

if [ "$HTTP_CODE" -ne 200 ]; then
    echo "FAIL: HTTP status $HTTP_CODE"
    exit 1
fi

if echo "$RESPONSE" | grep -q "$EXPECTED_CONTENT"; then
    echo "PASS: Found expected content"
    exit 0
else
    echo "FAIL: Expected content not found"
    exit 1
fi
```

### Health Check with Custom Headers

```bash
curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer {token}" \
    -H "Accept: application/json" \
    "{url}"
```

### Health Check API Endpoint (JSON)

```bash
#!/bin/bash
URL="{url}/health"

RESPONSE=$(curl -s "$URL")
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL")

if [ "$HTTP_CODE" -ne 200 ]; then
    echo "FAIL: HTTP status $HTTP_CODE"
    exit 1
fi

# Parse JSON health response
STATUS=$(echo "$RESPONSE" | jq -r '.status // "unknown"')
if [ "$STATUS" = "healthy" ] || [ "$STATUS" = "ok" ]; then
    echo "PASS: Service is $STATUS"
    exit 0
else
    echo "FAIL: Service status is $STATUS"
    exit 1
fi
```

### Multiple Endpoint Health Check

```bash
#!/bin/bash
ENDPOINTS=(
    "{url}"
    "{url}/api/health"
    "{url}/api/status"
)

FAILED=0

for ENDPOINT in "${ENDPOINTS[@]}"; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$ENDPOINT")
    if [ "$STATUS" -eq 200 ]; then
        echo "PASS: $ENDPOINT ($STATUS)"
    else
        echo "FAIL: $ENDPOINT ($STATUS)"
        FAILED=$((FAILED + 1))
    fi
done

if [ $FAILED -gt 0 ]; then
    echo "SUMMARY: $FAILED endpoints failed"
    exit 1
else
    echo "SUMMARY: All endpoints healthy"
    exit 0
fi
```

## Python Alternative

```python
#!/usr/bin/env python3
import requests
import sys

url = "{url}"
timeout = {timeout:-30}
expected_status = {expected_status:-200}

try:
    response = requests.get(url, timeout=timeout)
    if response.status_code == expected_status:
        print(f"PASS: {url} returned {response.status_code}")
        print(f"Response time: {response.elapsed.total_seconds():.3f}s")
        sys.exit(0)
    else:
        print(f"FAIL: {url} returned {response.status_code}")
        sys.exit(1)
except requests.exceptions.RequestException as e:
    print(f"FAIL: {url} - {str(e)}")
    sys.exit(1)
```

## Verification

Verify health check results:

```bash
# Check exit code of last command
echo $?  # 0 = success, non-zero = failure

# Run health check and capture result
if ./health-check.sh; then
    echo "Health check passed"
else
    echo "Health check failed"
fi
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Connection refused` | Service not running | Start the service or check port |
| `Connection timed out` | Network/firewall issue | Check firewall rules, increase timeout |
| `SSL certificate problem` | Invalid/expired cert | Use `-k` flag or fix certificate |
| `Could not resolve host` | DNS issue | Verify hostname/domain |
| `HTTP 502/503/504` | Upstream server error | Check backend service health |

## Notes

- Always set a reasonable timeout to avoid hanging
- Use retries for flaky network conditions
- Consider checking multiple endpoints for comprehensive health
- Include response time metrics for performance monitoring
- Health check endpoints should be lightweight (no heavy computation)
- Consider authentication for private health endpoints
- Log results to file for historical tracking
- Use exit codes for CI/CD integration
