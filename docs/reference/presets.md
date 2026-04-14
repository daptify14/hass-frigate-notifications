# Presets

Presets are starting templates that pre-fill your [profile](profiles/index.md) configuration during the wizard. All preset values are editable after profile creation.

## Built-in presets

The integration ships with six built-in presets.

> Message and subtitle values shown in the phase tables are template IDs. See [Templates](templates.md#built-in-templates) for the full Jinja2 behind each ID.

| ID | Display Name | Summary |
| ---- | ------------- | --------- |
| `simple` | Live Alerts | Recommended default -- instant alert, quiet follow-ups |
| `detailed` | Rich Alerts | Structured live alerts with phase icons and zone context |
| `notify_on_end` | End Only | One alert after the event ends |
| `snapshot_pager` | Snapshot Only | One immediate snapshot, no follow-ups |
| `latest_event` | Latest Only | Single rolling notification card |
| `activity_log` | Silent Log | Silent history in notification center only |

---

### Live Alerts (`simple`)

Basic detection alerts that work with any camera. Sends an immediate alert with a cropped snapshot, follows up with a GIF, and optionally delivers an AI summary.

| Phase | Message | Subtitle | Attachment | Sound / Interruption |
| ------- | --------- | ---------- | ------------ | ---------------------- |
| Initial | `object_only` + emoji | `merged_subjects` | snapshot_cropped | audible, active |
| Update | `object_only` + emoji, latest detection | `merged_subjects` | review_gif | none, active |
| End | inherits update (5s delay) | inherits update | inherits update | inherits update |
| GenAI | `genai_summary` | `merged_subjects` | review_gif | audible, passive |

### Rich Alerts (`detailed`)

Zone-aware alerts with phase icons. Uses `genai_disabled_overrides` to switch the end-phase message template when GenAI is off.

| Phase | Message | Subtitle | Attachment | Sound / Interruption |
| ------- | --------- | ---------- | ------------ | ---------------------- |
| Initial | `phase_icon_context` | `merged_subjects` | snapshot_cropped | audible, active |
| Update | `rich_update` (1s delay), latest detection | `merged_subjects` | review_gif | none, passive |
| End (GenAI on) | `genai_pending` (5s delay), latest detection | `merged_subjects` | inherits update | inherits update |
| End (GenAI off) | `phase_icon_context` (5s delay), latest detection | `merged_subjects` | inherits update | inherits update |
| GenAI | `phase_icon_genai_summary`, latest detection | `merged_subjects` | review_gif | audible, passive |

### End Only (`notify_on_end`)

Suppresses real-time alerts entirely. One audible notification per event when the review ends.

| Phase | Message | Subtitle | Attachment | Sound / Interruption |
| ------- | --------- | ---------- | ------------ | ---------------------- |
| Initial | disabled | -- | -- | -- |
| Update | disabled | -- | -- | -- |
| End | `object_action_zone` + emoji (5s delay), latest detection | `duration_summary` | review_gif | audible, active |
| GenAI | `genai_summary`, latest detection | (none) | review_gif | none, passive |

### Snapshot Only (`snapshot_pager`)

One snapshot, one sound, done. No follow-up notifications of any kind.

| Phase | Message | Subtitle | Attachment | Sound / Interruption |
| ------- | --------- | ---------- | ------------ | ---------------------- |
| Initial | `object_action_zone` + emoji | `merged_subjects` | snapshot_cropped | audible, active |
| Update | disabled | -- | -- | -- |
| End | disabled | -- | -- | -- |
| GenAI | disabled | -- | -- | -- |

### Latest Only (`latest_event`)

A single shared notification slot that always shows the most recent event. All profiles using this preset share tag `frigate-latest` and group `frigate`, so new events replace old ones.

| Phase | Message | Subtitle | Attachment | Sound / Interruption |
| ------- | --------- | ---------- | ------------ | ---------------------- |
| Initial | `single_subject` + emoji | `camera_zone` | snapshot_cropped | audible, active |
| Update | `single_subject` + emoji, latest detection | `camera_zone` | review_gif | none, passive |
| End | inherits update (5s delay) | inherits update | inherits update | inherits update |
| GenAI | `genai_summary`, latest detection | `camera_only_content` | review_gif | none, passive |

### Silent Log (`activity_log`)

Completely silent. Every phase uses `passive` interruption level -- no screen wake, no sound, no vibration, no banner. Notifications go straight to the notification center as visual history.

| Phase | Message | Subtitle | Attachment | Sound / Interruption |
| ------- | --------- | ---------- | ------------ | ---------------------- |
| Initial | `object_action_zone` + emoji | `merged_subjects` | thumbnail | none, passive |
| Update | `object_action_zone` + emoji, latest detection | `merged_subjects` | thumbnail | none, passive |
| End | inherits update (5s delay) | inherits update | review_gif | inherits update |
| GenAI | `genai_summary`, latest detection | (none) | review_gif | none, passive |

---

## How presets work

Presets use **sparse phases** -- only fields that differ from defaults are specified. The expansion order:

1. **Initial** -- merged with built-in initial defaults
2. **Update** -- merged with built-in update defaults
3. **End** -- merged with resolved update values (end inherits from update)
4. **GenAI** -- merged with built-in genai defaults

### GenAI auto-detection

GenAI capability is auto-detected from the linked Frigate config. When any camera on the linked Frigate instance has `review.genai.enabled`, the preset enables the GenAI phase; when capability is absent, GenAI sections are hidden and `genai_disabled_overrides` are applied automatically. Rich Alerts uses `genai_disabled_overrides` to swap its end-phase template when GenAI is unavailable. Other presets simply enable or disable the GenAI phase based on capability.

After profile creation, the stored config is authoritative. Reconfigure does not re-run preset branching -- changes to GenAI capability are reflected in conditional visibility of GenAI sections, not by re-applying the preset.

---

## Custom presets

Add custom presets as YAML files in:

```text
{HA config}/frigate_notifications/presets/
```

For example: `/config/frigate_notifications/presets/my_preset.yaml`

A custom preset with the same `id` as a built-in preset overrides it.

### YAML format

```yaml
schema_version: 1
id: my_custom_preset
version: 1
name: My Custom Preset
summary: Short one-line summary shown in the dropdown
description: >-
  Longer description shown when selected.
sort_order: 10

profile_defaults:
  tag: my-tag
  group: my-group

phases:
  initial:
    message_template: "{{ object }} detected on {{ camera_name }}"
    emoji_message: true
    interruption_level: active
    attachment: snapshot_cropped

  update:
    message_template: "{{ object }} still on {{ camera_name }}"
    interruption_level: active
    attachment: review_gif

  # end: omitted -- inherits from resolved update phase
  # genai: omitted -- uses built-in genai defaults

genai_disabled_overrides:
  end:
    message_template: "{{ object }} done on {{ camera_name }}"
```

### Required fields

| Field | Description |
| ------- | ------------- |
| `schema_version` | Must be `1`. |
| `id` | Unique identifier string. Lowercase snake_case recommended. |
| `version` | Integer version for your preset. |
| `name` | Display name shown in the dropdown. |
| `summary` | One-line summary shown below the name. |
| `phases.initial` | At minimum, the initial phase must be defined. |

### Optional fields

| Field | Description | Default |
| ------- | ------------- | --------- |
| `description` | Longer description shown when selected. | (empty) |
| `sort_order` | Position in dropdown. Lower = higher. | `99` |
| `profile_defaults` | Sets `tag` and/or `group` for the profile. | (none) |
| `phases.update` | Update phase config. | Built-in defaults |
| `phases.end` | End phase config. | Inherits from resolved update |
| `phases.genai` | GenAI phase config. | Built-in defaults |
| `genai_disabled_overrides` | Phase overrides applied when GenAI is off. | (none) |

### Phase fields

Each phase accepts these fields (all optional except where the phase requires them):

| Field | Type | Validation |
| ------- | ------ | ------------ |
| `message_template` | string | Template ID or custom Jinja2 |
| `subtitle_template` | string | Template ID or custom Jinja2 |
| `emoji_message` | boolean | |
| `emoji_subtitle` | boolean | |
| `sound` | string | |
| `volume` | float | `0.0` to `1.0` |
| `interruption_level` | string | `active`, `passive`, `time-sensitive` |
| `attachment` | string | `thumbnail`, `snapshot`, `snapshot_bbox`, `snapshot_cropped`, `snapshot_cropped_bbox`, `review_gif`, `event_gif` |
| `video` | string | `clip_hls`, `clip_mp4`, `review_gif_video`, `live_view`, `none` |
| `delay` | float | `0` to `300` seconds |
| `enabled` | boolean | |
| `critical` | boolean | |
| `use_latest_detection` | boolean | |

Unknown keys are rejected. If a file fails any validation check, it is skipped with a log warning and the integration continues loading other presets.

> **Schema versioning:** The `schema_version` field is checked against the integration's supported version (currently `1`). Files with a higher schema version are skipped with a warning, allowing forward compatibility.

### Security and trust model

Custom preset files are loaded from your local Home Assistant config directory. Treat this folder as administrator-controlled configuration. Preset templates are rendered through Home Assistant's template engine, so only trusted admins should author or modify preset files.
