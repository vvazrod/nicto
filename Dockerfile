FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

RUN mkdir /data
VOLUME /data

ENV NICTO_DATABASE_URL=sqlite+aiosqlite:////data/nicto.db \
    NICTO_API_HOST=0.0.0.0 \
    NICTO_API_PORT=8000

EXPOSE 8000

CMD ["nicto"]
