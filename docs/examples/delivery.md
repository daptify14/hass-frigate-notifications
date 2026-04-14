# Delivery

How to control where and how notifications arrive. Each example shows the minimum settings needed; see [Providers](../reference/providers.md) for platform details and [Notification Lifecycle](../reference/notification-lifecycle.md) for phase behavior.

## Different profiles for different people

Create multiple profiles on the same camera with different notify targets.

- **Profile 1**: "Driveway - Steve" targeting `notify.mobile_app_steve_iphone`, objects: all, severity: alert
- **Profile 2**: "Driveway - Sally" targeting `notify.mobile_app_sally_iphone`, objects: person only, severity: alert

Steve gets all alerts; Sally only gets person alerts.

---

## Silent updates with GIF

Configure the update phase for quiet animated previews.

In the profile's **Media & actions** section, configure the update phase:

- Attachment: Review GIF

In **Delivery & timing**, configure the update phase:

- Sound: `none`
- Volume: 0%
- Interruption: Passive

The update notification silently replaces the initial snapshot with an animated preview.

---

## Android phone notifications

Create a profile targeting an Android device.

**Basics:**

- Provider: Android (Companion)
- Device: select your Android phone

**Delivery & timing (Android delivery section):**

- Channel: `frigate_alerts` (create a matching channel on your phone via Companion App settings)
- Importance: `high`
- Sticky: On (notification stays until dismissed)

The integration emits both iOS and Android keys in every payload, so switching between providers requires no other changes.

---

## Family notify group

Send to multiple devices at once using a Home Assistant notify group.

1. Define a notify group in `configuration.yaml`:

   ```yaml
   notify:
     - name: family
       platform: group
       services:
         - service: mobile_app_steve_iphone
         - service: mobile_app_sally_pixel
   ```

2. In the profile's **Basics** step:
   - Provider: Cross-Platform (iOS + Android group)
   - Notify service: `notify.family`

Cross-Platform provider ensures both iOS and Android payload keys are included.
