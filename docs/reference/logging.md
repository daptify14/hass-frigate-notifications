# Logging Reference

Most integration log messages are at `debug` level. Enable debug logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.frigate_notifications: debug
```

## Filter rejections

The [filter chain](filtering.md) logs a specific rejection reason per profile. All rejections follow the pattern `Profile {name} rejected by {filter}: {reason}`:

| Filter | Reason example |
|--------|---------------|
| Severity | `severity detection != required alert` |
| Object | `objects ['dog'] not in required ['person', 'car']` |
| Sub-label (require) | `no verified objects present, recognition required` |
| Sub-label (include) | `no required sub_labels in ['unknown']` |
| Sub-label (exclude) | `excluded sub_labels ['john'] present` |
| Zone (any) | `zones ['yard'] have no overlap with required ['driveway']` |
| Zone (none present) | `no zones present, required ['driveway']` |
| Zone (all) | `zones ['yard'] missing required ['driveway']` |
| Zone (ordered) | `zones ['yard', 'driveway'] not in required order ['driveway', 'yard']` |
| Time | `current time 03:15 outside window 08:00-22:00` |
| State | `input_boolean.alarm state=off not in ['on']` |
| Presence | `person.john is home` |
| Silence | `silenced until 2025-06-15T14:30:00+00:00` |
| Switch | `switch switch.frigate_notifications_... is off` |
| Guard | `input_boolean.alarm is off` |
| Cooldown | `45s remaining for driveway` |

## Other key messages

| Log message | Meaning |
|-------------|---------|
| `New review abc... on driveway: objects=[...] zones=[...]` | Review received from MQTT |
| `NOTIFY new -> notify.mobile_app_... for review abc...` | Notification dispatched |
| `Update for unknown review ..., creating` | Update arrived for unseen review (normal) |
| `Review message too large (... bytes), dropping` | Payload exceeded 64 KB limit (warning) |
| `Cleaning up stale review ...` | Review idle for 30+ minutes, removed |
| `Failed to dispatch notification to ... for review ...` | Notify service call failed (exception) |
