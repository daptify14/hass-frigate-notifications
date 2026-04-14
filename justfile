# Justfile

# Default: list all recipes
default:
    @just --list --unsorted

# Run tests (pass args to filter, e.g. just test -k "test_zone")
test *ARGS:
    uv run pytest {{ ARGS }}

# Run tests against oldest supported HA (2025.6 / Py 3.13)
test-compat *ARGS:
    uv run --python 3.13 --project tests/env/compat pytest {{ ARGS }}

# Generate HTML coverage report
coverage: (test "--cov" "--cov-report=html" "-q")

# Lint with ruff (pass --fix to auto-fix)
lint *ARGS:
    uv run ruff check {{ ARGS }} .

# Format with ruff (pass --check to verify only)
fmt *ARGS:
    uv run ruff format {{ ARGS }} .

# Type check with ty
typecheck:
    uv run ty check --error-on-warning

# Full quality gate: lint + format check + typecheck + tests (95% coverage)
check: lint (fmt "--check") typecheck
    uv run pytest --cov --cov-report=xml --cov-fail-under=95

compose := "docker compose"
ha       := "homeassistant"

# Start dev services (HA + Frigate + MQTT + webhook catcher)
up *ARGS:
    {{ compose }} up -d {{ ha }} frigate mqtt webhook {{ ARGS }}

# Start with a fresh HA (skip pre-configured storage)
up-fresh *ARGS:
    HA_PRECONFIG=false just up {{ ARGS }}

# Stop dev services
down *ARGS:
    {{ compose }} down {{ ARGS }}

# Recreate HA dev container (re-runs preconfig)
restart:
    {{ compose }} up -d --force-recreate {{ ha }}

# Tail HA dev logs
logs *ARGS:
    {{ compose }} logs -f {{ ha }} {{ ARGS }}

# Shell into HA dev container
shell:
    {{ compose }} exec {{ ha }} bash

# Simulate a Frigate review lifecycle via MQTT (see --help for options)
simulate *ARGS:
    uv run python scripts/simulate_review.py {{ ARGS }}

# Tail webhook catcher logs (notification payloads)
notifications:
    scripts/tail_notifications.sh

# Serve docs locally (MkDocs Material)
docs *ARGS:
    uv run --group docs mkdocs serve --livereload {{ ARGS }}

# Build docs to site/
docs-build *ARGS:
    uv run --group docs mkdocs build {{ ARGS }}

# Set up local dev environment (deps + pre-commit hooks)
setup:
    scripts/setup.sh
