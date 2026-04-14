# Content & Templates

Content and templates control what each notification says. Per-phase message configuration -- each enabled phase appears as a collapsed section.

## Title template

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Title template** | Dropdown (custom value) | Select a built-in template or type custom Jinja2. Blank = uses global default. | (blank -- uses global) |

---

## Per-phase sections

Each phase section contains:

| Field | Type | Description |
| --- | --- | --- |
| **Enabled** | Boolean | Whether this phase sends notifications |
| **Message template** | Dropdown (custom value) | Select a built-in template or type custom Jinja2 |
| **Subtitle template** | Dropdown (custom value) | Select a built-in template or type custom Jinja2 |
| **Emoji to message** | Boolean | Per-item emoji injection in message context |
| **Emoji to subtitle** | Boolean | Per-item emoji injection in subtitle context |

Both template fields offer built-in templates in the dropdown, or accept custom Jinja2. See [Context Variables](../context-variables.md) for all available variables and [Templates](../templates.md) for the built-in template list.

The two emoji toggles are only shown when global emojis are enabled in [Global Defaults](../global-defaults.md). If global emojis are disabled, these toggles are hidden.

---

## GenAI section

!!! note "Conditional visibility"

    The GenAI section is only shown when GenAI is available for the selected cameras.

It contains the same fields as the other phase sections (enabled, message template, subtitle template, emoji toggles) plus one extra:

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Threat level prefix in title** | Boolean | Apply the global prefix text (configured in [Global Defaults](../global-defaults.md)) to the notification title based on threat level | On |

Prefix text for all three severity levels (0, 1, 2+) is configured globally. Profiles only control whether the prefix is applied.

---

## Zone phrase overrides

!!! note "Conditional visibility"

    Shown only for single-camera profiles where the camera has zones.

One text field per zone on the selected camera. Enter an action word or phrase (e.g., "entered", "arrived at", "near") to set the `zone_phrase` template variable. Leave blank to use the default ("detected").

Zone phrases can be Jinja2 templates, rendered with the full [context variables](../context-variables.md).
