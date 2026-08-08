# syntax=docker/dockerfile:1.12

ARG PYTHON_IMAGE=python:3.13.7-slim-bookworm@sha256:adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d
ARG DBMATE_IMAGE=ghcr.io/amacneil/dbmate:2.33.0@sha256:cbdf9e3631ff1c70a8a7a0091437bdd63c8525407009c2541273ee19e6eebc9e

FROM ${PYTHON_IMAGE} AS python-runtime

ARG UV_VERSION=0.11.19
ARG FFMPEG_DEBIAN_VERSION=7:5.1.9-0+deb12u1

ENV PATH="/opt/veridash/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/veridash/.venv

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        "ffmpeg=${FFMPEG_DEBIAN_VERSION}" \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir "uv==${UV_VERSION}" \
    && groupadd --gid 10001 veridash \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent veridash \
    && mkdir -p /opt/veridash /var/lib/veridash \
    && { \
        sha256sum /usr/bin/ffmpeg /usr/bin/ffprobe; \
        dpkg-query --show --showformat='${binary:Package}=${Version}\n' | sort; \
    } \
        | sha256sum \
        | sed 's/^/sha256:/' \
        | cut -d' ' -f1 \
        > /opt/veridash/FFMPEG_FINGERPRINT \
    && chown -R veridash:veridash /opt/veridash /var/lib/veridash

WORKDIR /opt/veridash

COPY --chown=veridash:veridash pyproject.toml uv.lock ./
COPY --chown=veridash:veridash apps/api/pyproject.toml apps/api/pyproject.toml
COPY --chown=veridash:veridash apps/scheduler/pyproject.toml apps/scheduler/pyproject.toml
COPY --chown=veridash:veridash apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY --chown=veridash:veridash libs/analysis/pyproject.toml libs/analysis/pyproject.toml
COPY --chown=veridash:veridash libs/core/pyproject.toml libs/core/pyproject.toml
COPY --chown=veridash:veridash libs/storage/pyproject.toml libs/storage/pyproject.toml
COPY --chown=veridash:veridash apps apps
COPY --chown=veridash:veridash libs libs

FROM python-runtime AS api
RUN uv sync --frozen --no-dev --package veridash-api \
    && rm -rf /root/.cache/uv
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["veridash-api"]

FROM python-runtime AS scheduler
RUN uv sync --frozen --no-dev --package veridash-scheduler \
    && rm -rf /root/.cache/uv
USER 10001:10001
ENTRYPOINT ["veridash-scheduler"]

FROM python-runtime AS worker
RUN uv sync --frozen --no-dev --package veridash-worker \
    && rm -rf /root/.cache/uv
USER 10001:10001
ENTRYPOINT ["veridash-worker"]

FROM python-runtime AS worker-gpu
RUN uv sync --frozen --no-dev --package veridash-worker --extra gpu \
    && rm -rf /root/.cache/uv
ENV LD_LIBRARY_PATH="/opt/veridash/.venv/lib/python3.13/site-packages/nvidia/cublas/lib:/opt/veridash/.venv/lib/python3.13/site-packages/nvidia/cudnn/lib"
USER 10001:10001
ENTRYPOINT ["veridash-worker"]

FROM ${DBMATE_IMAGE} AS migration
COPY db/migrations /opt/veridash/db/migrations
ENTRYPOINT ["/usr/local/bin/dbmate", "--migrations-dir", "/opt/veridash/db/migrations", "--no-dump-schema"]
CMD ["up"]
