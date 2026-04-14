# Context Variables

Variables available in all Jinja2 templates (message, title, subtitle, zone phrase overrides).

## Objects & subjects

Singular variables return the first item. Plural variables return all items comma-joined.

### `objects_raw`

Objects as Frigate sent them (raw), before any cleaning.

Example: `car-verified, person`

### `object_count`

Count of cleaned objects.

Example: `2`

### `object`

First cleaned object, title-cased. The `-verified` suffix is stripped and duplicates are removed.

Example: `Car`

### `objects`

All cleaned objects, comma-joined.

Example: `Car, Person`

### `sub_labels_raw`

Sub-labels as Frigate sent them (raw).

Example: `Bob's Car, Alice`

### `sub_label`

First cleaned sub-label, deduped.

Example: `Alice`

### `sub_labels`

All cleaned sub-labels, comma-joined.

Example: `Alice, Bob's Car`

### `subject`

**Primary variable.** Smart merge of objects and sub-labels: `-verified` entries are dropped entirely, remaining objects and sub-labels are deduped and title-cased.

Example: `Alice`

### `subjects`

All subjects, comma-joined.

Example: `Alice, Car`

### `added_subject`

Delta: new subjects since the last phase. Useful in update messages to show what changed.

Example: `Person`

---

## Zones & location

### `zones_raw`

Zones as Frigate sent them (raw).

Example: `front_yard, porch`

### `zone` / `first_zone`

First zone identifier (raw). `first_zone` is an alias.

Example: `front_yard`

### `last_zone`

Last zone identifier (raw).

Example: `porch`

### `zones`

All zones, humanized, comma-separated.

Example: `Front Yard, Porch`

### `zone_name` / `first_zone_name`

First zone, humanized. `first_zone_name` is an alias.

Example: `Front Yard`

### `last_zone_name`

Last zone, humanized.

Example: `Porch`

### `zone_alias`

First zone's friendly alias from the global [zone aliases](global-defaults.md#zone-aliases) configuration.

Example: `the Front Yard`

### `zone_text`

Zone override value from the profile's zone overrides, falls back to `zone_alias`.

Example: `the Front Yard`

### `zone_phrase`

Rendered zone phrase override (from the profile's Content & Templates section), or "detected" if no override is set.

Example: `crossed`

### `added_zones`

Zones added since the last update, humanized.

Example: `Porch`

### Zone phrase and zone alias

These two systems work together to build natural notification messages:

- **Zone alias** provides the location name (e.g., "the Front Yard"). Configured in integration options. See [Global Defaults](global-defaults.md#zone-aliases).
- **Zone phrase** provides the action word (e.g., "crossed"). Configured per-zone in the profile's Content & Templates section.

With the template `{{ object }} {{ zone_phrase }} {{ zone_alias }}`:

- `emoji_message: false` -> "Person crossed the Front Yard"
- `emoji_message: true` -> "👤 Person crossed the Front Yard"

---

## Camera & time

### `camera`

Camera identifier (raw).

Example: `driveway`

### `camera_name`

Humanized camera name.

Example: `Driveway`

### `profile_cameras`

All cameras in the profile, raw, comma-joined.

Example: `driveway, front_door`

### `profile_cameras_name`

All cameras in the profile, humanized, comma-joined.

Example: `Driveway, Front Door`

!!! note "Multi-camera profiles"

    `{{ camera }}` and `{{ camera_name }}` always reflect the camera that triggered the specific review. Use `{{ profile_cameras }}` or `{{ profile_cameras_name }}` for the full list of cameras in the profile.

### `time`

12-hour format.

Example: `3:45 PM`

### `time_24hr`

24-hour format.

Example: `15:45`

---

## Phase & lifecycle

### `phase`

Dispatch phase name.

Example: `initial`, `update`, `end`, `genai`

### `lifecycle`

Raw MQTT message type.

Example: `new`, `update`, `end`, `genai`

`phase` uses dispatch names (`initial` not `new`), while `lifecycle` uses raw MQTT names.

### `phase_emoji`

Emoji for the dispatch phase. Configured in [Appearance & Formatting](global-defaults.md#appearance-formatting).

### `is_initial` / `is_update` / `is_end` / `is_genai`

Boolean flags for the current phase.

Example: `True` / `False`

### `emoji`

Emoji for the first object (from the emoji map). Configured in [Appearance & Formatting](global-defaults.md#appearance-formatting).

---

## GenAI

### `genai_title`

AI-generated title.

Example: `Person pushing stroller down driveway`

### `genai_summary`

AI short summary.

Example: `A person pushes a stroller down the driveway...`

### `genai_scene`

Scene description.

Example: `A person is observed walking down the driveway...`

### `genai_confidence`

Confidence score.

Example: `0.95`

### `genai_threat_level`

Threat level.

Example: `0`, `1`, `2`

### `genai_concerns`

Comma-separated concerns.

Example: `unknown vehicle near garage`

### `genai_time`

GenAI event time.

Example: `Thursday, 11:49 AM`

---

## IDs & metadata

### `review_id`

Unique review identifier.

### `detection_id`

First detection ID.

### `detection_ids`

All detection IDs, comma-joined.

### `detection_count`

Number of detections.

Example: `3`

### `latest_detection_id`

Most recent detection ID.

### `base_url`

Home Assistant base URL.

### `frigate_url`

Frigate instance URL.

### `client_id`

Frigate client ID.

### `severity`

Review severity level.

Example: `alert`, `detection`

### `start_time` / `end_time`

Review timestamps.

### `duration`

Review duration in seconds.

Example: `45`

### `duration_human`

Review duration, human-readable. Empty if the review has not ended.

Example: `2m 34s`
