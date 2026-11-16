# The website's service (#961, docs/web.md): `docker build -t crafting-site .` then
# `docker run -p 8000:8000 -v crafting-site:/site crafting-site`.
# The volume holds the game data cache, the price file (`/site/data`, the configured price file name) and the store (`/site/output/web`).
# The service fetches its own prices every CRAFTING_PRICE_REFRESH_HOURS (OR-9, #1008): on an empty volume it fetches a price file first.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    CRAFTING_DATA_DIR=/site/data \
    CRAFTING_CACHE_DIR=/site/cache \
    CRAFTING_OUTPUT_DIR=/site/output \
    CRAFTING_WEB_HOST=0.0.0.0 \
    CRAFTING_WEB_PORT=8000 \
    CRAFTING_PRICE_REFRESH_HOURS=6

WORKDIR /app
COPY pyproject.toml uv.lock README.md crafting.toml ./
COPY src ./src
RUN uv sync --locked --no-dev --extra web

VOLUME /site
EXPOSE 8000

# the pinned game data is fetched once into the volume; then the server starts (one command)
CMD ["sh", "-c", "uv run --no-sync python -m crafting_system.data verify || uv run --no-sync python -m crafting_system.data fetch; exec uv run --no-sync python -m crafting_system.web"]
