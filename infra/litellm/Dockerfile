# LiteLLM proxy with TIP-aware secrets bootstrap.
#
# Pulls API keys from the TIP secrets vault at startup (via /internal/bootstrap-fetch)
# so they never live in docker-compose env, .env files, or the image. Operators
# rotate keys through the Settings UI; a `docker compose restart litellm` picks
# them up.

FROM ghcr.io/berriai/litellm:main-stable

# curl is needed by entrypoint.sh to hit the secrets vault.
# As of 2025/26, BerriAI ships LiteLLM on the Wolfi (Chainguard) base — apk,
# not apt. The image already has sh + sed but NOT curl. Single-line install
# keeps the layer thin.
USER root
RUN apk add --no-cache curl

COPY infra/litellm/config.yaml /etc/litellm/config.yaml
COPY infra/litellm/entrypoint.sh /usr/local/bin/tip-litellm-entrypoint
RUN chmod +x /usr/local/bin/tip-litellm-entrypoint

ENTRYPOINT ["/usr/local/bin/tip-litellm-entrypoint"]
