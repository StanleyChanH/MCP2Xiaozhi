# mcp2xiaozhi bridge — run any MCP server as a persistent service.
# https://github.com/StanleyChanH/MCP2Xiaozhi
#
# Usage:
#   1. Place mcp_config.json next to docker-compose.yml (or mount it).
#   2. Set MCP_ENDPOINT (and MCP_ENDPOINT_<NAME> per server) via env / .env.
#   3. docker compose up -d --build
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir mcp2xiaozhi

WORKDIR /app

# Mount your mcp_config.json here (read-only). See docker-compose.yml.
# Runs every enabled server; override CMD to target a single server, e.g.:
#   CMD ["mcp2xiaozhi", "run", "calculator"]
CMD ["mcp2xiaozhi", "run", "--all"]
