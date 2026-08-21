#!/usr/bin/env bash
# Client usage examples for a restricted gateway API key.
# Placeholders only — replace GATEWAY_HOST and load YOUR_API_KEY from a secret store.
set -euo pipefail

GATEWAY_HOST="${GATEWAY_HOST:-GATEWAY_HOST}"
# Prefer reading from the environment / secret mount — do not hardcode.
YOUR_API_KEY="${YOUR_API_KEY:?set YOUR_API_KEY from your secret store}"

echo "Preferred: header delivery (less likely to hit access-log query strings)"
curl -sS "https://${GATEWAY_HOST}/daily-visits?page=1&limit=5" \
  -H "X-API-Key: ${YOUR_API_KEY}" \
  -o /tmp/api-key-pattern-out.json \
  -w "HTTP %{http_code}\n"

echo "Some older OpenAPI specs use query key= — works but easier to leak via logs/history"
# curl -sS "https://${GATEWAY_HOST}/customer-lookup?customer_id=1&key=${YOUR_API_KEY}"

echo "Do not echo the key. Do not pass it on argv to long-lived process lists if you can avoid it."
echo "Response written to /tmp/api-key-pattern-out.json (body only)."
