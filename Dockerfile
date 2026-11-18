# API and worker images (ADR-015 §4). Pins: pins.toml [images]/[tools]. Build one target at a time:
#   docker build --target api -t cherrylove-api .
#   docker build --target worker -t cherrylove-worker .
FROM ghcr.io/astral-sh/uv:0.13.9 AS uv

FROM python:3.14.10-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/src \
    DJANGO_SETTINGS_MODULE=config.settings.production
WORKDIR /app
# Dependencies first (cached layer), exactly as locked, without dev tools.
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project && rm /usr/local/bin/uv
COPY manage.py ./
COPY config ./config
COPY src ./src
COPY contract ./contract
# Non-root at run time (ADR-015 §3).
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin cherrylove
USER 10001
EXPOSE 8000

FROM base AS api
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]

# The worker shares the code. Until the job queue exists it serves the same health probe; F1.15 switches its
# command to the django-tasks worker (keeping a probe) and F4.6 adds ffmpeg to this stage only (ADR-007 §8).
FROM base AS worker
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--access-logfile", "-"]
