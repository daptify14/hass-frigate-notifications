# Troubleshooting

## Verifying startup

With [debug logging enabled](#reading-logs), you should see after loading:

```
Setup complete for Frigate: 2 profiles, topic=frigate/reviews
```

If you don't see this, the integration failed to set up. Check below.

## Common startup failures

### "Frigate integration not ready yet -- will retry"

The Frigate integration hasn't loaded yet. Home Assistant will retry automatically, but you can also:

1. Check that the Frigate integration is healthy in Settings > Devices & Services
2. Manually reload: Settings > Devices & Services > Notifications for Frigate > three-dot menu > Reload

### Camera removed from Frigate

**Symptom**: a repair issue titled "Frigate camera binding is broken" appears, listing the camera name and affected profiles.

**Fix**: delete the affected profile device in Settings > Devices & Services > Notifications for Frigate, then optionally re-create it with a camera that exists in Frigate. The repair clears automatically when the camera is re-added or the stale profile is deleted.

### Zones changed in Frigate

**Symptom**: a repair issue titled "Zone configuration needs review" appears.

Zone aliases or profile zone overrides reference zones that no longer exist in Frigate.

1. Edit affected profiles: Content step > remove or update stale zone fields
2. Edit zone aliases: Settings > Devices & Services > Notifications for Frigate > Configure > zone aliases
3. The repair clears once all references point to current Frigate zones

## Notification not sending

Check these in order:

1. **Switch entity**: is the profile's switch entity turned on? Check the profile's device page in Settings > Devices & Services > Notifications for Frigate
2. **Silence**: is the profile silenced? Check the **Silenced until** datetime entity on the profile's device page. Press the **Clear silence** button to remove it, or wait for the timer to expire
3. **Severity filter**: does the review's severity match your profile? A `detection`-severity review won't trigger an `alert`-only profile. Set severity to `any` to test
4. **Object filter**: does the review contain objects your profile accepts? An empty filter means "all objects pass"
5. **Zone filter**: are required zones configured? The review must include a matching zone. Clear required zones temporarily to test
6. **Guard entity**: is the guard entity (if configured) in the ON state?
7. **Notify service**: is the mobile app device registered and online? Check Settings > Devices & Services > Mobile App. For Android TV, check the Android TV / Fire TV integration
8. **Logs**: [enable debug logging](#reading-logs) and check Settings > Logs. The filter chain logs exactly which filter rejected the review

## Reading logs

Most integration log messages are at `debug` level. Enable debug logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.frigate_notifications: debug
```

The filter chain logs exactly which filter rejected each review per profile. See [Logging Reference](reference/logging.md) for all filter rejection messages and other key log entries.

## MQTT not connected

If no reviews appear in logs:

1. Verify Frigate is producing reviews (check Frigate's web UI)
2. Confirm MQTT is added and configured: Settings > Devices & Services > MQTT
3. Check the **MQTT Connected** binary sensor entity created by the integration
4. Verify the subscribed topic matches Frigate's config (`frigate/reviews` by default)

## Android-specific issues

### No image in notification

Android requires the `image` key in the notification data. Verify the profile's provider is set to Android or Cross-Platform (not Apple). The integration emits Android-compatible image URLs only when the provider includes Android.

### HLS video not playing

Android does not support HLS streaming. When a phase uses Clip (HLS), the integration automatically falls back to `clip.mp4` for Android devices.

### Notification channel

Android notification behavior (sound, vibration, priority) is controlled by the notification channel. Set the channel name in the profile's Delivery step under Android delivery. Create matching channels on your Android device via the Companion App settings.

## Recognition filter not appearing

If the recognition filter section doesn't appear in the profile's Filtering step:

1. Verify your camera has face recognition or LPR enabled in Frigate
2. Verify faces have been trained in Frigate's UI or known plates are configured in Frigate's config
3. **Reload the Frigate integration** after training new faces or adding plates so the entity registry updates
4. Check for `sensor.frigate_*_recognized_face_*` or `sensor.frigate_*_recognized_plate_*` entities in Settings > Entities

The recognition filter uses the HA entity registry exclusively. If entities are missing, the section won't appear.

## GenAI section not appearing

If the GenAI section does not appear in the profile wizard or global Appearance step:

1. Verify GenAI is configured in Frigate itself
2. Verify the camera has GenAI enabled in Frigate's config (`review.genai.enabled: true`) or UI settings
3. Reload the Frigate integration so Home Assistant refreshes the cached Frigate config
4. Reload Notifications for Frigate

GenAI capability is detected from the Frigate config exposed by the Frigate integration

## Frigate integration reconfigured

If the underlying Frigate integration is reconfigured (URL, auth, SSL, IP, or port changes):

1. **Reload Notifications for Frigate** to rebuild runtime config from the updated Frigate data
2. **Verify Frigate URL** if you use the "Open Frigate" action button (check Global Defaults > Configure)
3. **Review camera/zone changes** if cameras or zones changed. Repair issues will surface for broken camera bindings and stale zones

If the Frigate instance was replaced entirely (new server, different camera set), delete and recreate the Notifications for Frigate entry instead.

## Known limitations

- **Sub-label filter: face/plate recognition only**: the sub-label filter discovers identities from Frigate's face recognition and LPR sensors only. Sub-labels from other sources (custom classification models, triggers with `classification_type: sub_label`) are not discoverable in the UI
- **Reviews-only architecture**: the integration subscribes to `frigate/reviews` only, not `frigate/events` or the Frigate HTTP API. All data comes from MQTT review messages
- **Zone data is append-only**: Frigate deduplicates zones at the review level. Re-entry through a previously visited zone doesn't re-append, so the zone list may not reflect the most recent position when using zone phrases.
- **Android TV: still images only**: Android TV notifications support static images (snapshot/thumbnail). GIF and video attachments are not supported
- **GenAI text is pre-rendered**: AI summary text comes from Frigate's GenAI metadata and is not processed through the template engine. Template variables do not apply inside GenAI content
- **Android video: HLS to MP4 fallback**: when HLS is configured for a phase, Android devices receive `clip.mp4` instead since Android does not support HLS in notifications

## Known issues

- **Datetime picker overflow on device page**: the "Silenced until" datetime picker may overflow its container on the device page, especially on narrow screens
