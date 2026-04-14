# Installation

## Prerequisites

Before installing Notifications for Frigate, make sure you have:

1. **Home Assistant** 2025.6 or newer
2. **Frigate NVR** v0.16.0 or newer (v0.17.0+ required for Generative AI summary notifications)
3. **MQTT** configured in Home Assistant and working for Frigate
4. **Frigate integration** installed and configured in Home Assistant
5. **iOS or Android Companion App** on your device (or Android TV / Fire TV integration for TV overlays)

> **Why MQTT matters:** this integration subscribes to Frigate review events from the `${topic_prefix}/reviews` MQTT topic (usually `frigate/reviews`).

## Install via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=daptify14&repository=hass-frigate-notifications)

Click the badge above, or add manually:

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three-dot menu (top right) and select **Custom repositories**
4. Paste the repository URL: `https://github.com/daptify14/hass-frigate-notifications`
5. Select **Integration** as the category and click **Add**
6. Close the custom repositories dialog
7. Search for "Notifications for Frigate" in the HACS integrations list
8. Click **Download** and confirm the version
9. Restart Home Assistant

## Manual installation

1. Download the [latest release](https://github.com/daptify14/hass-frigate-notifications/releases) from GitHub
2. Extract and copy the `custom_components/frigate_notifications` directory into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Setup

After installation and restart:

1. Go to Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Notifications for Frigate"
4. Select the Frigate instance to bind to (if you have multiple)
5. The integration is now active, proceed to [Getting started](getting-started.md) to create your first notification profile

> **Note:** The integration creates one config entry per Frigate instance. If you have multiple Frigate NVRs, add one entry per NVR.

## Removal

### Remove the integration

Settings > Devices & Services > Notifications for Frigate > three-dot menu > Delete.

### Uninstall the code

- **HACS**: HACS > Integrations > Notifications for Frigate > Remove
- **Manual**: delete the `custom_components/frigate_notifications` directory and restart HA

### What gets removed

Deleting the integration removes all associated devices, entities, config entry data, in-memory review state, and any active repair issues. MQTT subscriptions are cleaned up on unload. No files are written to disk beyond the HA config entry, so there is nothing else to clean up.
