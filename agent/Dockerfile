# the narrator worker; LiveKit takes an image, so this is how the agent ships
# built from the repository root, to preserve the library sitting beside it

FROM python:3.13-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

WORKDIR /app/agent

# dependencies before source, so editing a module does not reinstall the world
COPY agent/pyproject.toml agent/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY agent/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


FROM python:3.13-slim

WORKDIR /app/agent

# only the environment crosses over; uv has no business in a running worker
COPY --from=build /app/agent/.venv ./.venv
COPY agent/src ./src

# beside the agent, not inside it, exactly as in the repository
COPY library /app/library

ENV PATH="/app/agent/.venv/bin:$PATH"

RUN useradd --create-home narrator
USER narrator

CMD ["python", "-m", "narrator.main", "start"]
