# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime

ENV PATH="/app/backend/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app/backend

RUN groupadd --system pragma \
    && useradd --system --gid pragma --home-dir /app --shell /usr/sbin/nologin pragma

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/src ./src
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY themes /app/themes
COPY docker/backend/entrypoint.sh /usr/local/bin/pragma-backend

RUN uv sync --frozen --no-dev \
    && chmod +x /usr/local/bin/pragma-backend \
    && mkdir -p /app/modules /var/lib/pragma/media \
    && chown -R pragma:pragma /app /var/lib/pragma

USER pragma

EXPOSE 8000

ENTRYPOINT ["pragma-backend"]
CMD ["serve"]
