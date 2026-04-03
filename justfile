# Justfile

# Default: list all recipes
default:
    @just --list --unsorted

# Run tests (pass args to filter, e.g. just test -k "test_zone")
test *ARGS:
    uv run pytest {{ ARGS }}

# Lint with ruff (check only)
lint:
    uv run ruff check .

# Format with ruff
fmt:
    uv run ruff format .

# Auto-fix lint issues + format
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Type check with ty
typecheck:
    uv run ty check --error-on-warning

# Run tests against oldest supported HA (2025.6 / Py 3.13)
test-compat *ARGS:
    uv python install 3.13
    uv run --project tests/env/compat --python 3.13 pytest {{ ARGS }}

# Generate HTML coverage report and open in browser
coverage:
    uv run pytest --cov --cov-report=html -q
    open htmlcov/index.html

# Full quality gate: lint + format check + typecheck + tests (95% coverage)
check: lint && typecheck
    uv run ruff format --check .
    uv run pytest --cov --cov-report=xml --cov-fail-under=95

compose := "docker compose"
ha       := "homeassistant"

# Start dev services (HA + Frigate + MQTT + webhook catcher)
up *FLAGS:
    {{ compose }} up -d {{ ha }} frigate mqtt webhook {{ FLAGS }}

# Start with a fresh HA (skip pre-configured storage)
up-fresh *FLAGS:
    HA_PRECONFIG=false just up {{ FLAGS }}

# Stop dev services
down *FLAGS:
    {{ compose }} down {{ FLAGS }}

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

# Set up local dev environment (deps + pre-commit hooks)
setup:
    scripts/setup.sh
