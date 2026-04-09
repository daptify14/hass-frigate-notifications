# Context Variables

Variables available in all Jinja2 templates (message, title, subtitle, zone phrase overrides).

## Objects & subjects

| Variable | Description | Example |
| ---------- | ------------- | --------- |
| `{{ objects_raw }}` | Objects as Frigate sent them (raw) | `car-verified, person` |
| `{{ object_count }}` | Count of cleaned objects | `2` |
| `{{ object }}` | First cleaned object, title-cased. `-verified` suffix stripped, deduped. | `Car` |
| `{{ objects }}` | All cleaned objects, comma-joined | `Car, Person` |
| `{{ sub_labels_raw }}` | Sub-labels as Frigate sent them (raw) | `Bob's Car, Alice` |
| `{{ sub_label }}` | First cleaned sub-label, deduped | `Alice` |
| `{{ sub_labels }}` | All cleaned sub-labels, comma-joined | `Alice, Bob's Car` |
| `{{ subject }}` | **Primary variable.** Smart merge: `-verified` entries dropped entirely, remaining objects + sub-labels, deduped, title-cased. | `Alice` |
| `{{ subjects }}` | All subjects, comma-joined | `Alice, Car` |
| `{{ added_subject }}` | Delta: new subjects since last phase | `Person` |

Singular variables return the first item. Plural variables return all items comma-joined.

## Zones & location

| Variable | Description | Example |
| ---------- | ------------- | --------- |
| `{{ zones_raw }}` | Zones as Frigate sent them (raw) | `front_yard, porch` |
| `{{ zone }}` | First zone identifier (raw). Alias: `{{ first_zone }}` | `front_yard` |
| `{{ last_zone }}` | Last zone identifier (raw) | `porch` |
| `{{ zones }}` | All zones, humanized, comma-separated | `Front Yard, Porch` |
| `{{ zone_name }}` | First zone, humanized. Alias: `{{ first_zone_name }}` | `Front Yard` |
| `{{ last_zone_name }}` | Last zone, humanized | `Porch` |
| `{{ zone_alias }}` | First zone's friendly alias (from global zone aliases) | `the Front Yard` |
| `{{ zone_text }}` | Zone override value (from profile zone overrides), falls back to `zone_alias` | `the Front Yard` |
| `{{ zone_phrase }}` | Rendered zone phrase override or "detected" | `crossed` |
| `{{ added_zones }}` | Zones added since last update, humanized | `Porch` |

### Zone phrase and zone alias

These two systems work together to build natural notification messages:

- **Zone alias** provides the location name (e.g., "the Front Yard"). Configured in integration options. See [Global Defaults](global-defaults.md).
- **Zone phrase** provides the action word (e.g., "crossed"). Configured per-zone in the profile's Content & templates section.

With the template `{{ object }} {{ zone_phrase }} {{ zone_alias }}`:

- `emoji_message: false` -> "Person crossed the Front Yard"
- `emoji_message: true` -> "👤 Person crossed the Front Yard"

## Camera & time

| Variable | Description | Example |
| ---------- | ------------- | --------- |
| `{{ camera }}` | Camera identifier (raw) | `driveway` |
| `{{ camera_name }}` | Humanized camera name | `Driveway` |
| `{{ profile_cameras }}` | All cameras in the profile, raw, comma-joined | `driveway, front_door` |
| `{{ profile_cameras_name }}` | All cameras in the profile, humanized, comma-joined | `Driveway, Front Door` |
| `{{ time }}` | 12-hour format | `3:45 PM` |
| `{{ time_24hr }}` | 24-hour format | `15:45` |

> **Multi-camera profiles:** `{{ camera }}` and `{{ camera_name }}` always reflect the camera that triggered the specific review. Use `{{ profile_cameras }}` or `{{ profile_cameras_name }}` for the full list of cameras in the profile.

## Phase & lifecycle

| Variable | Description | Example |
| ---------- | ------------- | --------- |
| `{{ phase }}` | Dispatch phase | `initial`, `update`, `end`, `genai` |
| `{{ lifecycle }}` | Raw MQTT type | `new`, `update`, `end`, `genai` |
| `{{ phase_emoji }}` | Emoji for dispatch phase | see [Appearance & Formatting](global-defaults.md#appearance--formatting) |
| `{{ is_initial }}` / `{{ is_update }}` / `{{ is_end }}` / `{{ is_genai }}` | Boolean flags | `True` / `False` |
| `{{ emoji }}` | Emoji for first object (from emoji map) | see [Appearance & Formatting](global-defaults.md#appearance--formatting) |

Note: `phase` uses dispatch names (`initial` not `new`), while `lifecycle` uses raw MQTT names.

## GenAI

| Variable | Description | Example |
| ---------- | ------------- | --------- |
| `{{ genai_title }}` | AI-generated title | `Person pushing stroller down driveway` |
| `{{ genai_summary }}` | AI short summary | `A person pushes a stroller down the driveway, passing a parked white SUV, and exits the scene.` |
| `{{ genai_scene }}` | Scene description | `A person is observed walking down the driveway pushing a stroller...` |
| `{{ genai_confidence }}` | Confidence score | `0.95` |
| `{{ genai_threat_level }}` | Threat level | `0`, `1`, `2` |
| `{{ genai_concerns }}` | Comma-separated concerns | `unknown vehicle near garage` |
| `{{ genai_time }}` | GenAI event time | `Thursday, 11:49 AM` |

## IDs & metadata

| Variable | Description | Example |
| ---------- | ------------- | --------- |
| `{{ review_id }}` | Unique review identifier | |
| `{{ detection_id }}` | First detection ID | |
| `{{ detection_ids }}` | All detection IDs, comma-joined | |
| `{{ detection_count }}` | Number of detections | `3` |
| `{{ latest_detection_id }}` | Most recent detection ID | |
| `{{ base_url }}` | Home Assistant base URL | |
| `{{ frigate_url }}` | Frigate instance URL | |
| `{{ client_id }}` | Frigate client ID | |
| `{{ severity }}` | Review severity level | `alert`, `detection` |
| `{{ start_time }}` / `{{ end_time }}` | Review timestamps | |
| `{{ duration }}` | Review duration in seconds | `45` |
| `{{ duration_human }}` | Review duration, human-readable. Empty if not ended. | `2m 34s` |
