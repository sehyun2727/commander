# Commander sandbox image (Sprint 6).
#
# The ONLY place AI-generated code is ever executed -- and only inside a
# container built from this exact image, run with --network none and a
# non-root user (see docs/prompts/sprint-6.md "Security model"). No
# dependency installation happens at runtime: v1 supports the Python
# stdlib / Node built-ins + pytest only, all preinstalled here at build
# time, since containers run with no network.

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin sandbox \
    && mkdir -p /workspace \
    && chown sandbox:sandbox /workspace

WORKDIR /workspace
USER sandbox
