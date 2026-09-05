FROM python:3.13-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

WORKDIR /app/agent

COPY agent/pyproject.toml agent/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY agent/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM python:3.13-slim

WORKDIR /app/agent

COPY --from=build /app/agent/.venv ./.venv
COPY agent/src ./src

COPY library /app/library

ENV PATH="/app/agent/.venv/bin:$PATH"

RUN useradd --create-home narrator
USER narrator

CMD ["python", "-m", "narrator.main", "start"]
