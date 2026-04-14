# Reference

Complete behavior and field documentation for every part of the integration.

## Core concepts

**[Profiles](profiles.md)**: A profile connects cameras to a notification target (your phone, a device group, a TV). Each profile has its own filters, templates, and phase settings. A camera can belong to multiple profiles, so you can layer different notification strategies on the same camera.

**[Global defaults](global-defaults.md) & inheritance**: Shared settings that profiles can inherit from. Each option in a profile can inherit the global value, override it, or disable it entirely. Set your baseline in the integration options flow (reconfigure any time), then only customize what differs per profile.

**[Presets](presets.md)**: Starting templates that pre-fill a profile's configuration during the wizard. The integration ships with six (Live Alerts, Rich Alerts, End Only, Snapshot Only, Latest Only, Silent Log). All preset values are editable after profile creation.

**[Templates](templates.md)**: Notification titles, messages, and subtitles are Jinja2 templates with access to 40+ [context variables](context-variables.md) (camera name, detected objects, zones, severity, AI summaries, and more). Built-in templates cover common patterns; override at the profile or phase level for full control.

**[Filtering](filtering.md)**: Controls which reviews produce notifications. Filters cover object type, zone, severity, sub-labels, time of day, HA entity state, presence, cooldown, and more. Filters follow the same inheritance model as other profile settings.

## All reference topics

- **[Global Defaults](global-defaults.md)** -- shared settings that profiles inherit from
- **[Profiles](profiles.md)** -- every profile field, entities, and device details
- **[Presets](presets.md)** -- built-in presets and custom YAML presets
- **[Filtering](filtering.md)** -- the filter pipeline and profile inheritance model
- **[Notification Lifecycle](notification-lifecycle.md)** -- phases, dispatch, silence, and cooldown
- **[Context Variables](context-variables.md)** -- all template variables
- **[Templates](templates.md)** -- built-in templates, rendering, and notification URLs
- **[Actions](actions.md)** -- action buttons, tap actions, and custom HA actions
- **[Logging](logging.md)** -- filter rejection messages and key log entries
