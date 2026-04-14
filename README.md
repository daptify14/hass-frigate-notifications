# Notifications for Frigate

[![CI](https://github.com/daptify14/hass-frigate-notifications/actions/workflows/ci.yml/badge.svg)](https://github.com/daptify14/hass-frigate-notifications/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/daptify14/hass-frigate-notifications/graph/badge.svg)](https://codecov.io/gh/daptify14/hass-frigate-notifications) [![Docs](https://img.shields.io/badge/docs-mkdocs-blue)](https://daptify14.github.io/hass-frigate-notifications/)

A Home Assistant integration that delivers dynamic push notifications from [Frigate NVR](https://frigate.video) reviews to iOS, Android, and Android TV devices.

Extends the [Frigate integration](https://github.com/blakeblackshear/frigate-hass-integration). Set up notification profiles from built-in presets or customize everything through UI-based configuration flows.

**[Read the full documentation →](https://daptify14.github.io/hass-frigate-notifications/)**

## Features

- 4-phase notification lifecycle: initial alert, update, end-of-review, and optional GenAI summary
- Advanced filtering: zone, object type, sublabel, time of day, presence, entity state, and more
- Rich media: thumbnails, snapshots, event/review animated GIFs, video clips, or iOS live view attached per phase
- Template engine: 40+ context variables for messages, titles, action buttons, and tap behaviors
- Notification profiles for single or multi-camera setups
- Per-profile entities (switches, sensors, buttons) and repair issues for control and diagnostics
- Detects Generative AI support, trained faces, and known plates from your Frigate config

## Requirements

- Home Assistant 2025.6 or newer
- Frigate NVR v0.16.0+ (v0.17.0+ for Generative AI summaries)
- MQTT configured in Home Assistant
- [Frigate integration](https://github.com/blakeblackshear/frigate-hass-integration) installed in Home Assistant
- iOS or Android Companion App (or Android TV / Fire TV integration for TV overlays)

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=daptify14&repository=hass-frigate-notifications)

Click the badge above, or add manually:

1. Open HACS → **Integrations** → three-dot menu → **Custom repositories**
2. Paste `https://github.com/daptify14/hass-frigate-notifications`, select **Integration**, click **Add**
3. Search for "Notifications for Frigate" and click **Download**
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** and search for "Notifications for Frigate"

### Manual installation

1. Download the [latest release](https://github.com/daptify14/hass-frigate-notifications/releases) from GitHub
2. Copy `custom_components/frigate_notifications` into your HA `config/custom_components/` directory
3. Restart Home Assistant

See the [full installation guide](https://daptify14.github.io/hass-frigate-notifications/installation/) for details.

## Development

Requires [Python 3.14+](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/). [Just](https://github.com/casey/just) provides recipe shortcuts but isn't required — the underlying commands (`uv run pytest`, `uv run ruff check`, etc.) work directly. Optionally use the included devcontainer.

```sh
scripts/setup.sh          # install deps + pre-commit hooks (or: uv sync && uv run prek install)
just check                # lint, format, typecheck, test (95% coverage gate)
just up                   # start dev stack: HA, Frigate, MQTT, webhook catcher (docker compose)
just simulate             # send a test review lifecycle via MQTT (or use the VS Code "Test Notify" task for interactive picks)
```

Copy `.env.example` to `.env` to override versions. See `just --list` for all recipes.

## Acknowledgments

Inspired by [SgtBatten's Frigate Notification Blueprint](https://github.com/SgtBatten/HA_blueprints).

## License

MIT
