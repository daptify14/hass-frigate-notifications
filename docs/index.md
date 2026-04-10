# Overview

## How it works

Frigate publishes camera [reviews](https://docs.frigate.video/reference/review) over MQTT. This integration subscribes to that topic and walks each review through a notification pipeline:

1. **Processor** picks up the MQTT message and tracks the review's lifecycle (new, update, end)
2. **Filter chain** decides whether to notify - object type, severity, zones, sublabels, time of day, presence, and more
3. **Message builder** renders the notification using Jinja2 templates with context from the review (40+ context variables available)
4. **Provider** formats the payload for your platform (iOS, Android, or Android TV)
5. **Dispatcher** sends the notification via HA's notify service

Each review can trigger up to four notification phases: initial alert, update, end-of-review, and an optional GenAI summary.

## Core concepts

**Profiles**: A profile connects cameras to a notification target (your phone, a device group, a TV). Each profile has its own filters, templates, and phase settings. A camera can belong to multiple profiles, so you can layer different notification strategies on the same camera.

**Global defaults & inheritance**: Shared settings that profiles can inherit from. Each option in a profile can inherit the global value, override it, or disable it entirely. Set your baseline in the integration options flow (reconfigure any time), then only customize what differs per profile.

**Presets**: Starting templates that pre-fill a profile's configuration during the wizard. The integration ships with six (Live Alerts, Rich Alerts, End Only, Snapshot Only, Latest Only, Silent Log). All preset values are editable after profile creation.

**Templates**: Notification titles, messages, and subtitles are Jinja2 templates with access to 40+ context variables (camera name, detected objects, zones, severity, AI summaries, and more). Built-in templates cover common patterns; override at the profile or phase level for full control.

**Filtering**: Controls which reviews produce notifications. Filters cover object type, zone, severity, sub-labels, time of day, HA entity state, presence, cooldown, and more. Filters follow the same inheritance model as other profile settings. See [Filtering](reference/filtering.md) for the full filter chain.

## Full reference

### Setup

- [Installation](installation.md): HACS, manual install, and removal
- [Getting Started](getting-started.md): first profile walkthrough
- [Examples](examples.md): filtering, templates, and delivery examples
- [Troubleshooting](troubleshooting.md): common issues, logs, known limitations

### Configuration

- [Global Defaults](reference/global-defaults.md): shared options and inheritance
- [Profiles](reference/profiles.md): every profile field, entities, and device details
- [Presets](reference/presets.md): built-in presets and custom YAML presets
- [Filtering](reference/filtering.md): the filter pipeline and profile inheritance model

### Notifications

- [Notification Lifecycle](reference/notification-lifecycle.md): phases, dispatch, silence, and cooldown
- [Context Variables](reference/context-variables.md): all template variables
- [Templates](reference/templates.md): built-in templates, rendering, and notification URLs
- [Actions](reference/actions.md): action buttons, tap actions, and custom HA actions
- [Providers](reference/providers.md): iOS, Android, Android TV, and Cross-Platform
- [Logging Reference](reference/logging.md): filter rejection messages and key log entries
