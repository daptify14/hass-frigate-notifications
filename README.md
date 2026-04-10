# Notifications for Frigate

[![CI](https://github.com/daptify14/hass-frigate-notifications/actions/workflows/ci.yml/badge.svg)](https://github.com/daptify14/hass-frigate-notifications/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/daptify14/hass-frigate-notifications/graph/badge.svg?token=80TW54GVXD)](https://codecov.io/gh/daptify14/hass-frigate-notifications)

A Home Assistant integration that sends detailed push notifications from [Frigate NVR](https://frigate.video) cameras to iOS, Android, and Android TV devices.

Notifications can update in place as events progress — with configurable attachments (snapshots, GIFs, clips), zone-aware messages, and optional AI summaries. Use the included presets or fully customize each phase.

Inspired by [SgtBatten's Frigate Notification Blueprint](https://github.com/SgtBatten/HA_blueprints)

## Features

- Built-in notification presets, or fully customize your own profiles for single or multi-camera setups
- 4-phase notification lifecycle: initial alert, update, end-of-review, and GenAI summary — each fully customizable
- Configurable attachments, action buttons, tap actions, and message templates with 40+ context variables
- Filter notifications by zone, object type, sublabel, time of day, presence, and more
- Full Frigate Generative AI support for review summaries
- Per-profile entities (switches, sensors, buttons) and repair issues for invalid config

## Requirements

- Home Assistant 2025.6 or newer
- Frigate NVR with reviews enabled
- MQTT configured in Home Assistant
- [Frigate integration](https://github.com/blakeblackshear/frigate-hass-integration) installed in Home Assistant
- iOS or Android Companion App (or Android TV / Fire TV integration for TV overlays)

## Installation

1. Open HACS → **Integrations** → three-dot menu → **Custom repositories**
2. Paste `https://github.com/daptify14/hass-frigate-notifications`, select **Integration**, click **Add**
3. Search for "Notifications for Frigate" and click **Download**
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** and search for "Notifications for Frigate"

For manual installation and more details, see [docs/installation.md](docs/installation.md).

## Configuration

All configuration is done through the UI — no YAML required. A step-by-step wizard guides you through creating notification profiles, selecting cameras, choosing a preset, and customizing each phase.

- [Installation](docs/installation.md) — prerequisites, HACS/manual install, and removal
- [Getting Started](docs/getting-started.md) — first profile walkthrough
- [Troubleshooting](docs/troubleshooting.md) — common issues, logs, and limitations
- [Full reference](docs/index.md) — overview, features, and reference index

## Development

Requires [Python 3.14+](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/). [Just](https://github.com/casey/just) provides recipe shortcuts but isn't required — the underlying commands (`uv run pytest`, `uv run ruff check`, etc.) work directly. Optionally use the included devcontainer.

```sh
scripts/setup.sh          # install deps + pre-commit hooks (or: uv sync && uv run prek install)
just check                # lint, format, typecheck, test (95% coverage gate)
just up                   # start dev stack: HA, Frigate, MQTT, webhook catcher (docker compose)
just simulate             # send a test review lifecycle via MQTT (or use the VS Code "Test Notify" task for interactive picks)
```

Copy `.env.example` to `.env` to override versions. See `just --list` for all recipes.

## License

MIT
