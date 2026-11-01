# syntax=docker/dockerfile:1.7
#
# FALCON server image: the API, the console and the offline CLI in one image.
#
#   docker build -t falcon:1.0.0 .
#   docker run -p 8600:8600 -v falcon-data:/var/lib/falcon falcon:1.0.0
#   docker run --rm -v "$PWD:/work" -w /work falcon:1.0.0 scan . --format sarif --fail-on high
#
# Debian trixie ships OpenSSL 3.5, so the TLS probe can negotiate the hybrid
# X25519MLKEM768 group and the platform's own ML-KEM/ML-DSA code runs natively.

# ---------------------------------------------------------------- console
FROM node:26-alpine AS console
WORKDIR /build
COPY console/package.json console/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY console/ ./
RUN npm run build

# ------------------------------------------------------------------ server
FROM python:3.15-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FALCON_ENVIRONMENT=production \
    FALCON_HOST=0.0.0.0 \
    FALCON_PORT=8600 \
    FALCON_DATA_DIR=/var/lib/falcon \
    FALCON_CONSOLE_DIST=/opt/falcon/console \
    FALCON_SCAN_ROOTS='["/scan"]'

# git: repository sources. Nothing else from the distribution is needed at run time.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --gid 0 --home-dir /var/lib/falcon --shell /usr/sbin/nologin falcon \
 && mkdir -p /var/lib/falcon /scan \
 && chown 10001:0 /var/lib/falcon && chmod 0770 /var/lib/falcon

WORKDIR /opt/falcon
COPY server/pyproject.toml ./server/
COPY server/falcon ./server/falcon
RUN pip install ./server && rm -rf ./server
COPY --from=console /build/dist /opt/falcon/console

USER 10001
VOLUME ["/var/lib/falcon"]
EXPOSE 8600
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8600/api/v1/setup', timeout=4)" || exit 1

ENTRYPOINT ["falcon"]
CMD ["serve"]
