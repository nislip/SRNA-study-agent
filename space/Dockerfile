FROM ghcr.io/danny-avila/librechat-dev:latest
EXPOSE 3080

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=3080
ENV SESSION_EXPIRY=900000
ENV REFRESH_TOKEN_EXPIRY=604800000

# Create necessary directories
RUN mkdir -p /app/uploads/temp
RUN mkdir -p /app/client/public/images/temp
RUN mkdir -p /app/api/logs/
RUN mkdir -p /app/data

# Give write permission to the directory
RUN chmod -R 777 /app/uploads/temp
RUN chmod -R 777 /app/client/public/images
RUN chmod -R 777 /app/api/logs/
RUN chmod -R 777 /app/data

# Use this Space's own librechat.yaml
COPY librechat.yaml /app/librechat.yaml

# --- Medical calculator MCP server (Python, runs inside the Space over stdio) ---
# Source: https://github.com/u9401066/medical-calc-mcp (Apache-2.0). No API key needed.
# Installed under /app so the build can write there and the running app can read it.
ENV UV_PYTHON_INSTALL_DIR=/app/mcp-servers/.uv-python \
    UV_CACHE_DIR=/app/mcp-servers/.uv-cache
RUN command -v uv >/dev/null 2>&1 || (wget -qO- https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh)
RUN mkdir -p /app/mcp-servers/medical-calc \
 && (curl -fsSL -o /tmp/medical-calc-mcp.tar.gz https://github.com/u9401066/medical-calc-mcp/archive/refs/heads/main.tar.gz \
     || wget -qO /tmp/medical-calc-mcp.tar.gz https://github.com/u9401066/medical-calc-mcp/archive/refs/heads/main.tar.gz) \
 && tar -xzf /tmp/medical-calc-mcp.tar.gz -C /app/mcp-servers/medical-calc --strip-components=1 \
 && rm /tmp/medical-calc-mcp.tar.gz \
 && cd /app/mcp-servers/medical-calc \
 && uv sync --frozen --no-dev \
 && rm -rf /app/mcp-servers/.uv-cache \
 && chmod -R a+rX /app/mcp-servers

# Install dependencies
RUN cd /app/api && npm install

# Command to run on container start
CMD ["npm", "run", "backend"]
