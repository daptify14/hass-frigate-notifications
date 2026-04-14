# Android TV / Fire TV

Android TV uses the separate [Notifications for Android TV](https://www.home-assistant.io/integrations/nfandroidtv/) integration (not the Companion App). Notifications appear as a screen overlay.

## Settings

| Setting | Description | Default |
| --------- | ------------- | --------- |
| **Position** | Overlay position on screen. | `bottom-right` |
| **Font size** | Text size. | `medium` |
| **Duration** | How long the overlay stays visible (seconds). | `5` |
| **Transparency** | Overlay background transparency. | `0%` |
| **Interrupt** | Whether to interrupt current playback. | Off |
| **Timeout** | Provider timeout (seconds). | `30` |
| **Color** | Overlay accent color. | (none) |

## Limitations

- **Still images only** -- GIF and video attachments fall back to a cropped snapshot. The Android TV integration does not support animated media.
- **No action buttons** -- TV overlays cannot display interactive actions.
- **No grouping or tagging** -- each notification is an independent overlay; there's no notification history or stacking.
