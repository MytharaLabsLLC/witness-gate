# Witness Gate in a container

The container is the one-command delivery form: no local Python setup,
no virtualenv, no dependency hunting. The package has zero runtime
dependencies, so the image is just Python 3.12 (slim) plus this source.

## Build

```sh
docker build -t witness-gate .
```

## Run

```sh
docker run --rm -p 8765:8765 -v witness-gate-data:/home/gate witness-gate
```

That starts the HTTP gate server on port 8765. The named volume keeps
the sealed ledger (`gate-ledger.jsonl`) across runs; drop the `-v` flag
if you want a throwaway ledger.

## Why the server is the default command

A container is a service delivery form, and the HTTP gate server is the
service a customer actually runs: other systems POST candidate actions
to it and get judgments back. The quickstart is a demo, not a service,
so it is not the default. To run it (or any other console script)
inside the image instead:

```sh
docker run --rm witness-gate python /app/examples/quickstart.py
docker run --rm witness-gate witness-gate-mcp --help
```

## Equivalent install without Docker

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/witness-gate --host 127.0.0.1 --port 8765
```

Note: whoever can reach the port can ask for judgments. Keep the
server on a trusted network or behind your own access control, the
same caution that applies to any internal service.
