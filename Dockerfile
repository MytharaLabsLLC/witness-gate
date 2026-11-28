# Witness Gate: container delivery form.
# Builds the soulcradle package from pyproject.toml and runs the HTTP
# gate server as the default service. The package has zero runtime
# dependencies, so the image stays small and the build needs nothing
# beyond the base image and this source tree.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir . \
    && useradd --create-home gate

USER gate
WORKDIR /home/gate

EXPOSE 8765

# Default: the HTTP gate server (console script witness-gate,
# soul_cradle.gate_server:main). In a container the server binds
# 0.0.0.0 so the host can publish the port. The ledger is written to
# the working directory; mount a volume at /home/gate to keep it.
CMD ["witness-gate", "--host", "0.0.0.0", "--port", "8765"]
