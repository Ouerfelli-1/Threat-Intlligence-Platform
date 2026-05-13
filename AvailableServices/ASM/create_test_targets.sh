#!/bin/bash
# Curl commands to create scope with test targets and trigger active scans

BASE_URL="http://localhost:8000/api/v1"

echo "======================================================================"
echo "Creating scope for test targets"
echo "======================================================================"

# 1. Create Scope
curl -X POST "${BASE_URL}/scopes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-targets",
    "enabled": true,
    "description": "Test targets for active reconnaissance",
    "config": {
      "passive_enabled": true,
      "active_enabled": true,
      "passive_features": {
        "certificate_transparency": true,
        "dns_history": true,
        "osint_apis": true,
        "crtsh": true,
        "hackertarget": true,
        "virustotal": true
      },
      "active_features": {
        "subdomain_enumeration": true,
        "port_scanning": true,
        "http_probing": true,
        "cve_lookup": true,
        "technology_detection": true
      },
      "nmap": {
        "enabled": true,
        "scan_type": "fast",
        "threads": 5,
        "timeout": 600,
        "check_cves": true
      },
      "cve": {
        "enabled": true,
        "max_results_per_service": 20
      }
    }
  }' | jq '.'

echo ""
echo "======================================================================"
echo "Get the scope_id from above response and set it:"
echo "======================================================================"
read -p "Enter scope_id: " SCOPE_ID

echo ""
echo "======================================================================"
echo "Adding target: scanme.nmap.org"
echo "======================================================================"

# 2. Add scanme.nmap.org
curl -X POST "${BASE_URL}/scopes/${SCOPE_ID}/targets" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "domain",
    "value": "scanme.nmap.org",
    "enabled": true,
    "description": "Nmap official test target"
  }' | jq '.'

echo ""
echo "======================================================================"
echo "Adding target: example.com"
echo "======================================================================"

# 3. Add example.com
curl -X POST "${BASE_URL}/scopes/${SCOPE_ID}/targets" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "domain",
    "value": "example.com",
    "enabled": true,
    "description": "IANA example domain"
  }' | jq '.'

echo ""
echo "======================================================================"
echo "Adding target: owasp.org"
echo "======================================================================"

# 4. Add owasp.org
curl -X POST "${BASE_URL}/scopes/${SCOPE_ID}/targets" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "domain",
    "value": "owasp.org",
    "enabled": true,
    "description": "OWASP Foundation"
  }' | jq '.'

echo ""
echo "======================================================================"
echo "Creating scheduled active job (every 6 hours)"
echo "======================================================================"

# 5. Create schedule
curl -X POST "${BASE_URL}/scopes/${SCOPE_ID}/schedules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-targets-active-scan",
    "mode": "active",
    "cron_expression": "0 */6 * * *",
    "enabled": true,
    "description": "Active scan every 6 hours for test targets"
  }' | jq '.'

echo ""
echo "======================================================================"
echo "Triggering immediate active job"
echo "======================================================================"

# 6. Trigger immediate job
curl -X POST "${BASE_URL}/jobs?scope_id=${SCOPE_ID}&mode=active" \
  -H "Content-Type: application/json" | jq '.'

echo ""
echo "======================================================================"
echo "Setup complete!"
echo "======================================================================"
echo "View jobs: curl ${BASE_URL}/jobs | jq '.'"
echo "View scope: curl ${BASE_URL}/scopes | jq '.'"
