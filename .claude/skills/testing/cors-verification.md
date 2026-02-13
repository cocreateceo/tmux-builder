# CORS Verification Skill

## Purpose

Verify that Cross-Origin Resource Sharing (CORS) is correctly configured for deployed web applications. Catch CORS errors before users encounter them in production.

## Why CORS Matters

CORS errors are one of the most common deployment issues:
- API calls fail silently in browser
- Fonts don't load (cross-origin font blocking)
- Images from CDN don't display
- WebSocket connections rejected

## Prerequisites

- `curl` installed
- Target URL accessible
- Knowledge of expected origins (frontend domain)

## CORS Test Script

### Comprehensive CORS Test (Bash)

```bash
#!/bin/bash
# cors-verification.sh

TARGET_URL="${1:-https://api.example.com}"
ORIGIN="${2:-https://example.com}"
OUTPUT_FILE="${3:-cors-report.json}"

echo "=== CORS VERIFICATION ==="
echo "Target: $TARGET_URL"
echo "Origin: $ORIGIN"
echo ""

PASS=true
ISSUES=()

# Test 1: Simple GET with Origin header
echo "Test 1: Simple GET request with Origin header..."
RESPONSE=$(curl -s -I -X GET \
    -H "Origin: $ORIGIN" \
    "$TARGET_URL" 2>&1)

ACAO=$(echo "$RESPONSE" | grep -i "access-control-allow-origin" | tr -d '\r')
if [ -z "$ACAO" ]; then
    echo "  FAIL: No Access-Control-Allow-Origin header"
    ISSUES+=("Missing Access-Control-Allow-Origin header on GET")
    PASS=false
else
    echo "  PASS: $ACAO"
fi

# Test 2: Preflight OPTIONS request
echo ""
echo "Test 2: Preflight OPTIONS request..."
PREFLIGHT=$(curl -s -I -X OPTIONS \
    -H "Origin: $ORIGIN" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: Content-Type, Authorization" \
    "$TARGET_URL" 2>&1)

ACAO_PREFLIGHT=$(echo "$PREFLIGHT" | grep -i "access-control-allow-origin" | tr -d '\r')
ACAM=$(echo "$PREFLIGHT" | grep -i "access-control-allow-methods" | tr -d '\r')
ACAH=$(echo "$PREFLIGHT" | grep -i "access-control-allow-headers" | tr -d '\r')

if [ -z "$ACAO_PREFLIGHT" ]; then
    echo "  FAIL: No Access-Control-Allow-Origin on preflight"
    ISSUES+=("Missing ACAO header on OPTIONS preflight")
    PASS=false
else
    echo "  PASS: $ACAO_PREFLIGHT"
fi

if [ -z "$ACAM" ]; then
    echo "  WARN: No Access-Control-Allow-Methods header"
    ISSUES+=("Missing Access-Control-Allow-Methods header")
else
    echo "  PASS: $ACAM"
fi

if [ -z "$ACAH" ]; then
    echo "  WARN: No Access-Control-Allow-Headers header"
    ISSUES+=("Missing Access-Control-Allow-Headers header")
else
    echo "  PASS: $ACAH"
fi

# Test 3: Check for credentials support
echo ""
echo "Test 3: Credentials support..."
ACAC=$(echo "$RESPONSE" | grep -i "access-control-allow-credentials" | tr -d '\r')
if [ -n "$ACAC" ]; then
    echo "  INFO: $ACAC"

    # If credentials allowed, origin cannot be *
    if echo "$ACAO" | grep -q "\*"; then
        echo "  FAIL: Cannot use * with credentials"
        ISSUES+=("ACAO is * but credentials are allowed - invalid combination")
        PASS=false
    fi
else
    echo "  INFO: Credentials not explicitly allowed (may be intentional)"
fi

# Test 4: Check Max-Age for caching
echo ""
echo "Test 4: Preflight caching..."
ACMA=$(echo "$PREFLIGHT" | grep -i "access-control-max-age" | tr -d '\r')
if [ -n "$ACMA" ]; then
    echo "  PASS: $ACMA"
else
    echo "  INFO: No Access-Control-Max-Age (preflight not cached)"
fi

# Test 5: Test with actual fetch simulation
echo ""
echo "Test 5: Simulated browser fetch..."
FETCH_RESPONSE=$(curl -s -X POST \
    -H "Origin: $ORIGIN" \
    -H "Content-Type: application/json" \
    -w "\n%{http_code}" \
    "$TARGET_URL" -d '{}' 2>&1)

HTTP_CODE=$(echo "$FETCH_RESPONSE" | tail -1)
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "  PASS: POST request succeeded (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" -eq 405 ]; then
    echo "  INFO: POST not allowed (HTTP 405) - may be intentional"
else
    echo "  WARN: POST returned HTTP $HTTP_CODE"
fi

# Summary
echo ""
echo "=== SUMMARY ==="
if [ "$PASS" = true ] && [ ${#ISSUES[@]} -eq 0 ]; then
    echo "RESULT: PASS - CORS configured correctly"
    EXIT_CODE=0
else
    echo "RESULT: ISSUES FOUND"
    for issue in "${ISSUES[@]}"; do
        echo "  - $issue"
    done
    EXIT_CODE=1
fi

# Generate JSON report
cat > "$OUTPUT_FILE" << EOF
{
    "test": "cors_verification",
    "timestamp": "$(date -Iseconds)",
    "target_url": "$TARGET_URL",
    "test_origin": "$ORIGIN",
    "passed": $( [ "$PASS" = true ] && echo "true" || echo "false" ),
    "headers_found": {
        "access_control_allow_origin": "$( [ -n "$ACAO" ] && echo "true" || echo "false" )",
        "access_control_allow_methods": "$( [ -n "$ACAM" ] && echo "true" || echo "false" )",
        "access_control_allow_headers": "$( [ -n "$ACAH" ] && echo "true" || echo "false" )",
        "access_control_allow_credentials": "$( [ -n "$ACAC" ] && echo "true" || echo "false" )",
        "access_control_max_age": "$( [ -n "$ACMA" ] && echo "true" || echo "false" )"
    },
    "issues": [$(printf '"%s",' "${ISSUES[@]}" | sed 's/,$//')]
}
EOF

echo ""
echo "Report saved to: $OUTPUT_FILE"
exit $EXIT_CODE
```

## Testing Static Assets (S3/CloudFront)

### Test Font Loading

```bash
#!/bin/bash
# test-font-cors.sh

FONT_URL="${1:-https://cdn.example.com/fonts/myfont.woff2}"
ORIGIN="${2:-https://example.com}"

echo "Testing font CORS: $FONT_URL"

RESPONSE=$(curl -s -I \
    -H "Origin: $ORIGIN" \
    "$FONT_URL")

ACAO=$(echo "$RESPONSE" | grep -i "access-control-allow-origin")

if [ -n "$ACAO" ]; then
    echo "PASS: Font has CORS headers"
    echo "  $ACAO"
else
    echo "FAIL: Font missing CORS headers"
    echo "  Fonts require CORS to load cross-origin"
    exit 1
fi
```

### Test Image Loading

```bash
#!/bin/bash
# test-image-cors.sh

IMAGE_URL="${1:-https://cdn.example.com/images/photo.jpg}"
ORIGIN="${2:-https://example.com}"

echo "Testing image CORS: $IMAGE_URL"

RESPONSE=$(curl -s -I \
    -H "Origin: $ORIGIN" \
    "$IMAGE_URL")

CONTENT_TYPE=$(echo "$RESPONSE" | grep -i "content-type")
ACAO=$(echo "$RESPONSE" | grep -i "access-control-allow-origin")

echo "Content-Type: $CONTENT_TYPE"

if [ -n "$ACAO" ]; then
    echo "PASS: Image has CORS headers (needed for canvas manipulation)"
else
    echo "INFO: Image missing CORS headers"
    echo "  Images load without CORS, but canvas operations will fail"
fi
```

## Common CORS Issues and Fixes

| Issue | Symptom | Fix |
|-------|---------|-----|
| No CORS headers | "Blocked by CORS policy" in console | Add CORS headers to server/CDN |
| Wrong origin | Origin not in allowed list | Add origin to allow list or use * |
| Missing preflight | OPTIONS returns 404/405 | Configure server to handle OPTIONS |
| Credentials with * | "Cannot use wildcard with credentials" | Use specific origin instead of * |
| Missing headers | "Request header not allowed" | Add to Access-Control-Allow-Headers |

## AWS S3 CORS Configuration

```json
[
    {
        "AllowedOrigins": ["https://example.com", "https://www.example.com"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["*"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3600
    }
]
```

Apply with:
```bash
aws s3api put-bucket-cors \
    --bucket my-bucket \
    --cors-configuration file://cors.json
```

## CloudFront CORS Configuration

For CloudFront, you need to:
1. Configure origin S3 bucket with CORS
2. Forward Origin header in CloudFront behavior
3. Cache based on Origin header

```bash
# Check if CloudFront forwards Origin header
aws cloudfront get-distribution-config --id DISTRIBUTION_ID \
    --query 'DistributionConfig.DefaultCacheBehavior.ForwardedValues.Headers'
```

## Verification Checklist

- [ ] API endpoints return CORS headers
- [ ] Preflight (OPTIONS) requests handled
- [ ] Fonts load from CDN
- [ ] Images accessible for canvas operations
- [ ] WebSocket connections work (if applicable)
- [ ] All required methods allowed
- [ ] All required headers allowed
- [ ] Credentials handled correctly

## Integration

Run CORS verification:
- After API deployment
- After CDN configuration changes
- When adding new origins
- As part of health check suite
