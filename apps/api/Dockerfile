# UnSeal API image. Build context is apps/api.
#
#   docker build -t unseal-api apps/api                      # default stage: test (runtime + dev tools + tests)
#   docker build --target runtime -t unseal-api-runtime apps/api   # slim image for deployment
#
# WeasyPrint shapes Tamil and Devanagari through Pango and HarfBuzz, which the slim base image lacks,
# so real PDF rendering (tests/pdf) runs here rather than on a developer machine without Pango.
# The Noto fonts ship inside the package (src/unseal/pdf/fonts), so no system fonts are needed.

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_FROZEN=1

# Runtime libraries named in the WeasyPrint install docs for Debian.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.11.13

RUN useradd --create-home --uid 10001 app \
    && mkdir /app \
    && chown app:app /app
USER app
WORKDIR /app

# Dependencies first so this layer is cached until pyproject.toml or uv.lock changes.
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

COPY --chown=app:app src ./src
RUN uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "unseal.main:app", "--host", "0.0.0.0", "--port", "8000"]


# Test image: adds the dev group (pytest, ruff, mypy) and the tests. This is the last stage, so it is
# what a plain `docker build` produces.
FROM runtime AS test
RUN uv sync
COPY --chown=app:app tests ./tests
CMD ["uv", "run", "pytest", "-q", "tests/pdf"]
