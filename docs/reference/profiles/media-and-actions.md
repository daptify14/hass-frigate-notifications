# Media & Actions

Media and actions control what each notification shows and what users can tap. Per-phase media configuration -- only phases enabled in Content & Templates appear here.

## Attachments

Each phase section contains:

| Field | Type | Description |
| --- | --- | --- |
| **Attachment** | Dropdown | Thumbnail, Snapshot, Snapshot (bounding box), Snapshot (cropped), Snapshot (cropped + bbox), Review GIF, Event GIF |
| **Video** | Dropdown | None (use attachment), Clip (HLS), Clip (MP4), Review GIF video, Live View (iOS). Shown when provider supports video. |
| **Use latest detection** | Boolean | Use latest detection ID for media URLs (not shown for initial phase) |

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

Options: View Clip, View Snapshot, View GIF, View Live Stream, Open HA (App), Open HA (Browser), Open Frigate, No Action (Android).

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
