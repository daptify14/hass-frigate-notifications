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

> Built-in templates use short IDs in config storage. When you select a template from the dropdown, the ID is stored and resolved to the full Jinja2 at render time. You can also type custom Jinja2 directly into the dropdown field -- custom templates are stored and rendered as-is.

All examples below assume a person detected on a camera named "Driveway" in a zone aliased to "the Driveway" with zone phrase "entered".

### Message templates

| ID | Label | Template | Phases | Example |
| ---- | ------- | ---------- | -------- | --------- |
| `object_action_zone` | Object + action + zone | `{{ object }} {{ zone_phrase }} {{ zone_alias }}` | all | 👤 Person entered the Driveway |
| `phase_icon_context` | Phase icon + context | `{{ phase_emoji }} {{ object }} {{ zone_phrase }} {{ zone_alias }}` | all | 🆕 Person entered the Driveway |
| `object_zone_only` | Object + zone only | `{{ object }} in {{ zone_alias }}` | all | 👤 Person in the Driveway |
| `object_zone_phrase` | Object + action (no zone) | `{{ object }} {{ zone_phrase }}` | all | 👤 Person entered |
| `merged_subjects` | Merged subjects | `{{ subjects }}` | all | Alice, Car |
| `object_only` | Object only | `{{ object }} detected` | all | 👤 Person detected |
| `single_subject` | Single subject | `{{ subject }}` | all | 👤 Person |
| `rich_update` | Rich update (new line) | `{{ phase_emoji }} {{ object }} ... / {{ added_subject }} detected` | update, end | 🔄 Person entered the Driveway / Car detected |
| `zone_info` | Zone info | `{{ zone_alias }}` | all | the Driveway |
| `update_delta` | Update delta | `{{ added_subject }} detected` | update, end | Car detected |
| `camera_zone` | Camera + zone | `{{ camera_name }} {{ zone_alias }}` | all | Driveway the Driveway (works best when camera and zone names differ) |
| `camera_only_content` | Camera only | `{{ camera_name }}` | all | Driveway |
| `duration_summary` | Duration summary | `Duration: {{ duration }}s` | end | Duration: 12s |
| `genai_summary` | GenAI summary | `{{ genai_summary }}` | genai | A person pushes a stroller down the driveway, passing a parked white SUV, and exits the scene. |
| `phase_icon_genai_summary` | Phase icon + GenAI summary | `{{ phase_emoji }} {{ genai_summary }}` | genai | ✨ A person pushes a stroller down the driveway, passing a parked white SUV, and exits the scene. |
| `genai_pending` | GenAI pending placeholder | `{{ phase_emoji }} Pending AI Summary` | end | 🔚 Pending AI Summary |
| `genai_scene` | GenAI scene | `{{ genai_scene }}` | genai | A person is observed walking down the driveway pushing a stroller... |
| `genai_summary_concerns` | GenAI summary + concerns | `{{ genai_summary }}` + `{{ genai_concerns }}` | genai | Car departs the driveway and exits the frame. / unknown vehicle near garage |

### Title templates

| ID | Label | Template | Example |
| ---- | ------- | ---------- | --------- |
| `camera_time` | Camera + time (default) | `{{ camera_name }} - {{ time }}` | Driveway - 3:45 PM |
| `camera_time_24hr` | Camera + 24hr time | `{{ camera_name }} - {{ time_24hr }}` | Driveway - 15:45 |
| `camera_only` | Camera only | `{{ camera_name }}` | Driveway |
| `camera_object` | Camera + object | `{{ camera_name }} - {{ object }}` | Driveway - Person |
| `camera_subject` | Camera + subject | `{{ camera_name }} - {{ subject }}` | Driveway - Alice |
| `genai_title` | GenAI title | `{{ genai_title }}` | Person pushing stroller down driveway |
| `camera_genai_title` | Camera + GenAI title | `{{ camera_name }} - {{ genai_title }}` | Driveway - Person pushing stroller down driveway |
| `camera_genai_title_time` | Camera + GenAI title + time | `{{ camera_name }} - {{ genai_title }} ({{ genai_time }})` | Driveway - Person pushing stroller down driveway (Thursday, 11:49 AM) |

### Zone phrase options

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
