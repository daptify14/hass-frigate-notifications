# Media & Actions

Media and actions control what each notification shows and what users can tap. Per-phase media configuration -- only phases enabled in Content & Templates appear here.

## Attachments

Each phase section contains:

| Field | Type | Description |
| --- | --- | --- |
| **Attachment** | Dropdown | Thumbnail, Snapshot, Snapshot (bounding box), Snapshot (cropped), Snapshot (cropped + bbox), Review GIF, Event GIF |
| **Video** | Dropdown | None (use attachment), Clip (HLS), Clip (MP4), Review GIF video, Live View (iOS). Shown when provider supports video. |
| **Use latest detection** | Boolean | Use latest detection ID for media URLs (not shown for initial phase) |
| **Tap action** | Dropdown | Inherit profile (default), or any [tap action](#tap-action) option to use for this phase only. Shown when provider supports action presets. |
| **Custom URL** | Text | Used when this phase's tap action is Custom URL |

Android TV profiles use a reduced attachment selector appropriate for overlay display.

---

## Custom actions

!!! note "Conditional visibility"

    Shown when the provider supports custom actions.

One HA action selector per phase (initial, update, end, GenAI).

---

## Tap action

!!! note "Conditional visibility"

    Shown when the provider supports action presets.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Tap action preset** | Dropdown | What opens when you tap the notification | View Clip |
| **Custom URL** | Text | Used by the Custom URL preset. A full http(s) URL, or a path such as `/dashboard-cameras/live` that opens inside the Companion App | (empty) |

Options: View Clip, View Snapshot, View GIF, View Live Stream, Open HA (App), Open HA (Browser), Open Frigate, Custom URL, No Action (Android).

A phase can override the profile tap action in its own section above, for example a live dashboard on initial and update with the clip on end. See [when each target works](../actions.md#when-each-tap-target-works).

---

## Action buttons

!!! note "Conditional visibility"

    Shown when the provider supports action presets.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Button 1** | Dropdown | First action button preset | View Clip |
| **Button 2** | Dropdown | Second action button preset | View Snapshot |
| **Button 3** | Dropdown | Third action button preset | Silence Notifications |

Options: View Clip, View Snapshot, View GIF, View Live Stream, Silence Notifications, Open HA (App), Open HA (Browser), Open Frigate, Custom Action, No Action (Android), None (empty slot).

---

## Custom button action

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Custom button action** | Action selector | HA action that fires when a button slot is set to "Custom Action" | (empty) |

See [Actions](../actions.md) for details.
