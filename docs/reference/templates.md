# Templates

Notification titles, messages, and subtitles support Jinja2 templates via Home Assistant's built-in template engine. Templates have access to [context variables](context-variables.md) describing the review, camera, objects, zones, phase, and AI analysis.

## How rendering works

Templates are rendered in a single pass:

1. **Context assembly** -- the full context dictionary is built with all variables.
2. **Zone phrase rendering** -- zone phrase overrides (e.g., "entered", "near") are Jinja2 templates rendered against the full context. The rendered result replaces `{{ zone_phrase }}`.
3. **Message / title / subtitle rendering** -- each template is rendered once with the full context.

Zone phrase templates can reference any context variable:

```jinja2
{{ object }} entered
```

This renders to something like "Car entered" before being inserted into the message via `{{ zone_phrase }}`. If you want emoji in the final message/subtitle, use the per-phase **Emoji in message** / **Emoji in subtitle** toggles.

## Override chain

Templates resolve in this order (highest priority first):

1. **Phase-level template** -- set per-phase in the profile's Content & templates section
2. **Profile title template** -- set at the profile level (title only)
3. **Global default** -- from integration options or built-in defaults

This lets you use `{{ genai_summary }}` for the GenAI phase while keeping the default template for other phases.

## Built-in templates

Dropdown options for message, title, and subtitle fields. See [Presets](presets.md) for the profile preset system, which is separate.

!!! note "Template IDs vs custom Jinja2"

    Built-in templates use short IDs in config storage. When you select a template from the dropdown, the ID is stored and resolved to the full Jinja2 at render time. You can also type custom Jinja2 directly into the dropdown field -- custom templates are stored and rendered as-is.

All examples below assume a person detected on a camera named "Driveway" in a zone aliased to "the Driveway" with zone phrase "entered".

---

## Message templates

### `object_action_zone`

Object + action + zone. All phases.

`{{ object }} {{ zone_phrase }} {{ zone_alias }}`

**Example:** 👤 Person entered the Driveway

---

### `phase_icon_context`

Phase icon + context. All phases.

`{{ phase_emoji }} {{ object }} {{ zone_phrase }} {{ zone_alias }}`

**Example:** 🆕 Person entered the Driveway

---

### `object_zone_only`

Object + zone only. All phases.

`{{ object }} in {{ zone_alias }}`

**Example:** 👤 Person in the Driveway

---

### `object_zone_phrase`

Object + action (no zone). All phases.

`{{ object }} {{ zone_phrase }}`

**Example:** 👤 Person entered

---

### `merged_subjects`

Merged subjects. All phases.

`{{ subjects }}`

**Example:** Alice, Car

---

### `object_only`

Object only. All phases.

`{{ object }} detected`

**Example:** 👤 Person detected

---

### `single_subject`

Single subject. All phases.

`{{ subject }}`

**Example:** 👤 Person

---

### `rich_update`

Rich update with delta on new line. Update and end phases.

`{{ phase_emoji }} {{ object }} ... / {{ added_subject }} detected`

**Example:** 🔄 Person entered the Driveway / Car detected

---

### `zone_info`

Zone info. All phases.

`{{ zone_alias }}`

**Example:** the Driveway

---

### `update_delta`

Update delta. Update and end phases.

`{{ added_subject }} detected`

**Example:** Car detected

---

### `camera_zone`

Camera + zone. All phases. Works best when camera and zone names differ.

`{{ camera_name }} {{ zone_alias }}`

**Example:** Driveway the Driveway

---

### `camera_only_content`

Camera only. All phases.

`{{ camera_name }}`

**Example:** Driveway

---

### `duration_summary`

Duration summary. End phase.

`Duration: {{ duration }}s`

**Example:** Duration: 12s

---

### `genai_summary`

GenAI summary. GenAI phase.

`{{ genai_summary }}`

**Example:** A person pushes a stroller down the driveway, passing a parked white SUV, and exits the scene.

---

### `phase_icon_genai_summary`

Phase icon + GenAI summary. GenAI phase.

`{{ phase_emoji }} {{ genai_summary }}`

**Example:** ✨ A person pushes a stroller down the driveway, passing a parked white SUV, and exits the scene.

---

### `genai_pending`

GenAI pending placeholder. End phase.

`{{ phase_emoji }} Pending AI Summary`

**Example:** 🔚 Pending AI Summary

---

### `genai_scene`

GenAI scene. GenAI phase.

`{{ genai_scene }}`

**Example:** A person is observed walking down the driveway pushing a stroller...

---

### `genai_summary_concerns`

GenAI summary + concerns. GenAI phase.

`{{ genai_summary }}` + `{{ genai_concerns }}`

**Example:** Car departs the driveway and exits the frame. / unknown vehicle near garage

## Title templates

### `camera_time`

Camera + time. Default title template.

`{{ camera_name }} - {{ time }}`

**Example:** Driveway - 3:45 PM

---

### `camera_time_24hr`

Camera + 24-hour time.

`{{ camera_name }} - {{ time_24hr }}`

**Example:** Driveway - 15:45

---

### `camera_only`

Camera name only.

`{{ camera_name }}`

**Example:** Driveway

---

### `camera_object`

Camera + detected object.

`{{ camera_name }} - {{ object }}`

**Example:** Driveway - Person

---

### `camera_subject`

Camera + subject (with sub-label).

`{{ camera_name }} - {{ subject }}`

**Example:** Driveway - Alice

---

### `genai_title`

GenAI-generated title. GenAI phase.

`{{ genai_title }}`

**Example:** Person pushing stroller down driveway

---

### `camera_genai_title`

Camera + GenAI title. GenAI phase.

`{{ camera_name }} - {{ genai_title }}`

**Example:** Driveway - Person pushing stroller down driveway

---

### `camera_genai_title_time`

Camera + GenAI title + time. GenAI phase.

`{{ camera_name }} - {{ genai_title }} ({{ genai_time }})`

**Example:** Driveway - Person pushing stroller down driveway (Thursday, 11:49 AM)

---

## Zone phrase options

Used as zone phrase overrides in the profile's Content & templates section. These slot into the `{{ zone_phrase }}` variable.

| Phrase | Example message |
| -------- | ----------------- |
| `at` | Person at the Porch |
| `near` | Person near the Garage |
| `entered` | Car entered the Driveway |
| `left` | Person left the Porch |
| `arrived at` | Person arrived at the Porch |
| `spotted near` | Car spotted near the Garage |
| `approaching` | Person approaching the Porch |
| `leaving` | Car leaving the Driveway |
| `passing through` | Car passing through the Driveway |
| `crossing` | Person crossing the Front Yard |
| `detected in` | Person detected in the Backyard |
| `outside` | Person outside the Garage |
| `seen at` | Car seen at the Driveway |

---

## Notification URLs

The per-phase attachment selector determines the image or animation attached to each notification. The per-phase video selector can override the attachment with a video clip.

### Attachment types

| Type | URL pattern | Notes |
| ------ | ------------- | ------- |
| Thumbnail | `/thumbnail.jpg` | Small preview |
| Snapshot | `/snapshot.jpg` | Full-resolution still |
| Snapshot with bounding box | `/snapshot.jpg?bbox=1` | Still with detection overlay |
| Snapshot cropped | `/snapshot.jpg?crop=1` | Cropped to detected object (default initial) |
| Snapshot cropped + bbox | `/snapshot.jpg?bbox=1&crop=1` | Cropped + overlay |
| Review GIF | `/review_preview.gif` | Animated review (default update/end/genai) |
| Event GIF | `/event_preview.gif` | Animated event preview |

### Video types (optional override)

| Type | Format | Notes |
| ------ | -------- | ------- |
| Review GIF (video) | MP4 | Review preview as MP4 with player controls |
| Clip MP4 | MP4 | Recorded clip, must fully download before playback |
| Clip HLS | HLS streaming | Progressive playback, iOS only (Android falls back to MP4) |
| Live View | Camera stream | iOS only, opens live stream in notification |

All URLs route through `{{ base_url }}/api/frigate{{ client_id }}/notifications`.
