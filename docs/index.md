# Notifications for Frigate

A Home Assistant integration that delivers enriched push notifications for [Frigate NVR](https://docs.frigate.video/) camera reviews.

## Features

- **Notification profiles** for single or multi-camera setups with independent filters, templates, and delivery settings
- **Advanced filtering** by object type, zone, severity, sub-labels, time of day, presence, entity state, cooldown, and more
- **Rich media** attachments per phase -- thumbnails, snapshots, animated GIFs, video clips, or iOS live view
- **Jinja2 templates** with 40+ context variables for messages, titles, action buttons, and tap behaviors
- **iOS, Android, and Android TV / Fire TV** support with platform-specific payload formatting
- **Built-in presets** to get started quickly, with full customization available after creation
- **GenAI summaries** as an optional fourth notification phase (requires Frigate v0.17.0+)

## Getting started

1. **[Installation](setup/installation.md)** -- install via HACS or manually, then add the integration
2. **[Getting Started](setup/getting-started.md)** -- set your URLs, create a profile, and test your first notification

## How it works

Frigate publishes camera [reviews](https://docs.frigate.video/reference/review) over MQTT. This integration subscribes to that topic and walks each review through a notification pipeline:

1. **Processor** picks up the MQTT message and tracks the review's lifecycle (new, update, end)
2. **Filter chain** decides whether to notify -- object type, severity, zones, sublabels, time of day, presence, and more
3. **Message builder** renders the notification using Jinja2 templates with context from the review (40+ context variables available)
4. **Provider** formats the payload for your platform (iOS, Android, or Android TV)
5. **Dispatcher** sends the notification via HA's notify service

Each review can trigger up to four notification phases: initial alert, update, end-of-review, and an optional GenAI summary.
