#!/usr/bin/env bash
# Point abbyresnick.com at GitHub Pages via the GoDaddy API.
#
# Your token is typed into a hidden prompt — it is never passed as an argument,
# never written to disk, and never lands in your shell history.
#
# Create a token: https://developer.godaddy.com  →  Personal Access Tokens
#   Scope needed: domains.dns:update  (or the "Domains & DNS" bundle)
#
# Run:  bash scripts/wire-dns.sh

set -euo pipefail

DOMAIN="abbyresnick.com"
PAGES_HOST="yoniversefilms.github.io"
API="https://api.godaddy.com/v1/domains/${DOMAIN}"

read -rsp "Paste your GoDaddy PAT (input hidden): " GD_TOKEN; echo
[ -n "${GD_TOKEN}" ] || { echo "No token entered. Aborting."; exit 1; }

auth=(-H "Authorization: Bearer ${GD_TOKEN}" -H "Content-Type: application/json")

echo
echo "── Current A records for ${DOMAIN} ──"
code=$(curl -sS -o /tmp/gd_now.json -w '%{http_code}' "${auth[@]}" "${API}/records/A/@" || true)
if [ "$code" = "401" ] || [ "$code" = "403" ]; then
  echo "Auth failed (HTTP $code)."
  echo "Check the token is valid and has the domains.dns:update scope."
  exit 1
elif [ "$code" != "200" ]; then
  echo "Unexpected response (HTTP $code):"; cat /tmp/gd_now.json; exit 1
fi
cat /tmp/gd_now.json; echo

echo "This will REPLACE the root A records with GitHub Pages' four addresses,"
echo "and point www at ${PAGES_HOST}."
read -rp "Proceed? (y/N) " ok
[[ "$ok" =~ ^[Yy]$ ]] || { echo "Cancelled — nothing changed."; exit 0; }

echo
echo "→ Setting A records…"
curl -sS -X PUT "${API}/records/A/@" "${auth[@]}" -d '[
  {"data":"185.199.108.153","ttl":3600},
  {"data":"185.199.109.153","ttl":3600},
  {"data":"185.199.110.153","ttl":3600},
  {"data":"185.199.111.153","ttl":3600}
]' -w 'HTTP %{http_code}\n'

echo "→ Setting www CNAME…"
curl -sS -X PUT "${API}/records/CNAME/www" "${auth[@]}" -d "[
  {\"data\":\"${PAGES_HOST}\",\"ttl\":3600}
]" -w 'HTTP %{http_code}\n'

unset GD_TOKEN
rm -f /tmp/gd_now.json

echo
echo "Done. DNS usually propagates in 10–30 minutes. Check with:"
echo "  dig +short ${DOMAIN}"
echo
echo "Note: GoDaddy 'Domain Forwarding' can override these records — if the"
echo "parking page persists, turn forwarding off in the GoDaddy dashboard."
