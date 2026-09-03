# The narrator worker. LiveKit takes an image, so this is how the agent actually ships.
# Built from the repository root, because the worker reads the story library that sits
# beside it and the image has to preserve that layout.

FROM python:3.13-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

WORKDIR /app/agent

# Dependencies resolve from the lockfile before any source is copied, so editing a
# module does not reinstall the world. The download cache is mounted rather than
# copied, so it speeds up a rebuild without ending up in a layer.
COPY agent/pyproject.toml agent/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY agent/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


FROM python:3.13-slim

WORKDIR /app/agent

# Only the environment crosses over. uv itself has no business in a running worker.
COPY --from=build /app/agent/.venv ./.venv
COPY agent/src ./src

# Beside the agent, not inside it, exactly as in the repository.
COPY library /app/library

ENV PATH="/app/agent/.venv/bin:$PATH"

RUN useradd --create-home narrator
USER narrator

CMD ["python", "-m", "narrator.main", "start"]
