# Templates

How to customize notification messages with Jinja2 templates and context variables. Each example shows the minimum settings needed; see [Templates](../reference/templates.md) for built-in templates and [Context Variables](../reference/context-variables.md) for the full variable list.

## Basic person alert

A simple profile that notifies whenever a person is detected on the front door camera.

**Basics:**

- Camera: `front_door`
- Objects: `person`
- Severity: `alert`

**Content & templates:**

- Message template: `{{ object }} {{ zone_phrase }} {{ zone_alias }}`
- Emoji in message: on

**Result:**

- No zones configured: "👤 Person detected"
- With zones (e.g. `front_yard`): "👤 Person detected Front Yard" (auto-generated alias)
- With zone phrase override + alias: "👤 Person arrived at the Front Door"

---

## Zone-aware messages

Set up zone phrase overrides to describe what's happening.

1. In the profile's **Content & templates** section, set zone phrase overrides:
   - `front_yard`: "entered"
   - `garage`: "near"
   - `porch`: "at"

2. In integration options, set zone aliases:
   - `front_yard`: "the Driveway"
   - `garage`: "the Garage"
   - `porch`: "the Front Door"

3. With the message template `{{ object }} {{ zone_phrase }} {{ zone_alias }}` and emoji in message enabled:
   - "👤 Person entered the Driveway"
   - "🚘 Car near the Garage"
   - "👤 Person at the Front Door"

---

## Rich alerts with phase emoji

Use the **Rich Alerts** preset for detailed multi-phase notifications.

**Key template variables:**

- `{{ phase_emoji }}` -- phase indicator (🆕 🔄 🔚 ✨)
- `{{ subject }}` / `{{ subjects }}` -- detected object(s) with sub-labels applied
- `{{ added_subject }}` -- newly detected object in update messages

**Example title template:** `{{ phase_emoji }} {{ camera_name }}`

**Example update message:** `{{ added_subject }} also detected` -- shows what changed since the initial notification.

**Example flow:**

- 🆕 Person entered the Driveway
- 🔄 Person entered the Driveway / Car detected
- 🔚 Pending AI Summary
- ✨ A person walked down the driveway and got into a parked car.

---

## AI summary with threat prefixes

Enable GenAI notifications to get AI-written summaries when GenAI is available on your Frigate setup.

1. In integration options under **Appearance**, configure the global GenAI title prefixes:
   - Severity 0: (optional, often left blank)
   - Severity 1: ⚡
   - Severity 2+: ⚠️
2. In the profile's **Content & templates** section, expand the GenAI section and leave **Threat level prefix in title** enabled
3. In **Delivery & timing**, set the GenAI phase interruption level to "Passive" (arrives quietly)

**Result:** A notification arrives after the AI analysis:

- Title: "⚠️ Driveway - 3:15 PM" (if threat level 2+)
- Message: "Unknown person approached the front door and lingered for 45 seconds."
