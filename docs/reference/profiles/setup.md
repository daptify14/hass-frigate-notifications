# Setup

Setup walks through creating a profile: preset, cameras, provider, and target.

## Preset

Select a starting template. [Presets](../presets.md) pre-fill phase configs, templates, and defaults for common notification patterns. All values are editable after creation.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Preset** | Dropdown | Starting template: Live Alerts, Rich Alerts, End Only, Snapshot Only, Latest Only, Silent Log | Live Alerts |

If any of the profile's selected cameras has GenAI review descriptions enabled in Frigate, GenAI sections appear automatically throughout the wizard. See [Presets](../presets.md#genai-auto-detection) for details.

---

## Basics

Profile identity, camera selection, provider, and notification target. This step runs in two passes: the first collects identity and provider, the second collects the target.

### Pass 1: Identity

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Profile name** | Text | Descriptive label for this profile | (required) |
| **Cameras** | Multi-select | Frigate cameras to monitor (one or more) | (required) |
| **Provider** | Dropdown | Apple (iOS Push), Android (Companion), Cross-Platform (iOS + Android group), Android TV / Fire TV | Apple (iOS Push) |

### Pass 2: Target

After selecting a provider, the step reloads to show provider-appropriate target fields:

| Field | Type | Description | Shown for |
| --- | --- | --- | --- |
| **Device** | Device picker | Mobile app device to notify | Apple, Android |
| **Notify service** | Dropdown (custom value) | Notify service or group name | All providers |
| **Tag** | Text | Notification tag template | Apple, Android, Cross-Platform |
| **Group** | Text | Notification group template | Apple, Android, Cross-Platform |

Exactly one of Device or Notify service must be filled. Tag and Group are hidden for Android TV.

!!! note "Grouping for multi-camera profiles"

    The default `{{ camera }}` in the group template resolves to the triggering camera, so each camera's notifications group independently even within a multi-camera profile.

---

## Customize menu

After Basics, the wizard presents a menu. Pick any section to configure or go straight to **Save**:

- **Filtering** -- objects, zones, guard, time, presence, state
- **Content & templates** -- message templates, subtitles, emoji, zone phrases
- **Media & actions** -- attachments, video, action buttons
- **Delivery & timing** -- sound, timing, rate limiting, platform options
- **Save profile** -- save with current settings

Every section returns to the menu after saving, so you can visit them in any order or skip entirely. On reconfigure, the menu also includes **Basics** for editing the notification target.
