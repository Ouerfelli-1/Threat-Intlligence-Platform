#!/usr/bin/env sh
# Fetch every AI provider API key from the TIP secrets vault, export as env vars,
# then launch the LiteLLM proxy. This way operators rotate keys via the Settings
# UI (encrypted at rest in secrets), and the proxy just needs a restart to pick
# them up — keys never live in docker-compose or a .env file.

set -eu

: "${SECRETS_URL:=http://secrets:8012}"
: "${SECRETS_BOOTSTRAP_TOKEN:?SECRETS_BOOTSTRAP_TOKEN is required}"
: "${LITELLM_CONFIG_PATH:=/etc/litellm/config.yaml}"
: "${LITELLM_PORT:=4000}"

echo "[litellm-entrypoint] waiting for secrets service at $SECRETS_URL ..."
attempts=0
until curl -fsS "$SECRETS_URL/health" >/dev/null 2>&1; do
  attempts=$((attempts + 1))
  if [ "$attempts" -gt 60 ]; then
    echo "[litellm-entrypoint] secrets unreachable after 60s, exiting"
    exit 1
  fi
  sleep 1
done
echo "[litellm-entrypoint] secrets reachable"

# Fetch one secret via the bootstrap endpoint (no JWT required — pre-auth path
# used during service startup). Returns empty string if the secret isn't set.
fetch_secret() {
  name="$1"
  body="$(printf '{"service_name":"litellm","bootstrap_token":"%s","secret_name":"%s"}' \
    "$SECRETS_BOOTSTRAP_TOKEN" "$name")"
  resp="$(curl -fsS -X POST "$SECRETS_URL/internal/bootstrap-fetch" \
    -H 'Content-Type: application/json' -d "$body" 2>/dev/null || echo '')"
  if [ -z "$resp" ]; then
    echo ""
    return
  fi
  # Extract "value":"..." from the JSON response without pulling in jq.
  printf '%s' "$resp" | sed -n 's/.*"value":"\([^"]*\)".*/\1/p'
}

echo "[litellm-entrypoint] fetching API keys from secrets vault..."

for KEY in GITHUB_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY GROQ_API_KEY \
           GEMINI_API_KEY MISTRAL_API_KEY COHERE_API_KEY OPENROUTER_API_KEY \
           TOGETHER_API_KEY DEEPSEEK_API_KEY; do
  v="$(fetch_secret "$KEY")"
  if [ -n "$v" ]; then
    export "$KEY=$v"
    # Log only the first 8 chars so log scraping doesn't leak the key
    visible="$(printf '%s' "$v" | cut -c1-8)"
    echo "[litellm-entrypoint]   loaded $KEY ($visible...)"
  fi
done

# Master key auth for clients calling the proxy. If missing, generate an
# ephemeral one and log a warning — fine for dev, deploy-time should always
# supply a real one.
MASTER="$(fetch_secret LITELLM_MASTER_KEY)"
if [ -z "$MASTER" ]; then
  MASTER="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  echo "[litellm-entrypoint] WARN: LITELLM_MASTER_KEY not in secrets vault; using ephemeral key"
fi
export LITELLM_MASTER_KEY="$MASTER"
echo "[litellm-entrypoint]   master key set (length=${#MASTER})"

echo "[litellm-entrypoint] starting litellm proxy on :$LITELLM_PORT"
exec litellm --config "$LITELLM_CONFIG_PATH" --port "$LITELLM_PORT" --host 0.0.0.0
