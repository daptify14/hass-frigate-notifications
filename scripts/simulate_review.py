#!/usr/bin/env python3
"""Simulate a Frigate review lifecycle by publishing MQTT messages.

Publishes new → update → end → genai messages to frigate/reviews,
matching the exact payload shapes Frigate sends.

Usage:
    just simulate                          # default: person+car on driveway
    just simulate --camera front_door      # different camera
    just simulate --objects person,dog      # different objects
    just simulate --sub-labels Bob          # sub-labels on update
    just simulate --no-genai               # skip genai phase
    just simulate --delay 2                # faster lifecycle
"""

import argparse
from datetime import UTC, datetime
import json
import time
import uuid

import paho.mqtt.client as mqtt

TOPIC = "frigate/reviews"


def short_id() -> str:
    """Return a 6-char hex string."""
    return uuid.uuid4().hex[:6]


def make_detection_id() -> str:
    """Generate a realistic Frigate detection ID (timestamp-suffix)."""
    t = time.time() - (10 * (0.5 - (int.from_bytes(uuid.uuid4().bytes[:2]) / 65535)))
    return f"{t:.6f}-{short_id()}"


def build_review_data(
    detection_ids: list[str],
    objects: list[str],
    sub_labels: list[str],
    zones: list[str],
    *,
    thumb_time: float | None = None,
    metadata: dict | None = None,
) -> dict:
    """Build the `data` block of a review before/after payload."""
    return {
        "detections": list(detection_ids),
        "objects": list(objects),
        "verified_objects": [o for o in objects if "-verified" in o],
        "sub_labels": list(sub_labels),
        "zones": list(zones),
        "audio": [],
        "thumb_time": thumb_time,
        "metadata": metadata,
    }


def build_payload(
    msg_type: str,
    review_id: str,
    camera: str,
    start_time: float,
    before_severity: str,
    after_severity: str,
    before_data: dict,
    after_data: dict,
    *,
    end_time: float | None = None,
) -> dict:
    """Build a complete Frigate review MQTT payload."""
    thumb = f"/media/frigate/clips/review/thumb-{camera}-{review_id}.webp"
    return {
        "type": msg_type,
        "before": {
            "id": review_id,
            "camera": camera,
            "start_time": start_time,
            "end_time": end_time if msg_type in ("end", "genai") else None,
            "severity": before_severity,
            "thumb_path": thumb,
            "data": before_data,
        },
        "after": {
            "id": review_id,
            "camera": camera,
            "start_time": start_time,
            "end_time": end_time if msg_type in ("end", "genai") else None,
            "severity": after_severity,
            "thumb_path": thumb,
            "data": after_data,
        },
    }


def run(args: argparse.Namespace) -> None:
    """Connect to MQTT and publish a full review lifecycle."""
    objects = [o.strip() for o in args.objects.split(",")]
    zones = [z.strip() for z in args.zones.split(",")]
    sub_labels = (
        [s.strip() for s in args.sub_labels.split(",") if s.strip()] if args.sub_labels else []
    )

    now = time.time()
    review_id = f"{now:.6f}-{short_id()}"
    det_ids = [make_detection_id() for _ in range(len(objects))]
    thumb_time = now + 0.5

    now_dt = datetime.fromtimestamp(now, tz=UTC).strftime("%A, %I:%M %p")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"simulate-review-{short_id()}",
    )
    client.connect(args.host, args.port)
    client.loop_start()

    def publish(payload: dict, label: str) -> None:
        """Publish payload to MQTT and log."""
        msg = json.dumps(payload)
        client.publish(TOPIC, msg)
        print(f"  [{label}] → {TOPIC} ({len(msg)} bytes)")

    print(f"Review {review_id}")
    print(f"  camera={args.camera} severity=detection→{args.severity}")
    print(f"  objects={objects} zones={zones} sub_labels={sub_labels}")
    print()

    # Phase 1: new — before and after are identical (matches Frigate source)
    new_data = build_review_data(det_ids[:1], objects[:1], [], zones[:1], thumb_time=thumb_time)
    publish(
        build_payload(
            "new",
            review_id,
            args.camera,
            now,
            "detection",
            "detection",
            new_data,
            new_data,
        ),
        "new",
    )

    time.sleep(args.delay)

    # Phase 2: update — accumulate all objects + zones + sub_labels, escalate severity
    if len(objects) > 1 or len(zones) > 1 or sub_labels:
        after_update = build_review_data(
            det_ids,
            objects,
            sub_labels,
            zones,
            thumb_time=thumb_time,
        )
        publish(
            build_payload(
                "update",
                review_id,
                args.camera,
                now,
                "detection",
                args.severity,
                new_data,
                after_update,
            ),
            "update",
        )
        time.sleep(args.delay)
        last_data = after_update
    else:
        last_data = new_data

    # Phase 3: end — set end_time
    end_time = time.time()
    publish(
        build_payload(
            "end",
            review_id,
            args.camera,
            now,
            args.severity,
            args.severity,
            last_data,
            last_data,
            end_time=end_time,
        ),
        "end",
    )

    # Phase 4: genai (optional)
    if not args.no_genai:
        time.sleep(args.delay)
        obj_label = " and ".join(objects)
        zone_label = ", ".join(z.replace("_", " ") for z in zones)
        genai_metadata = {
            "title": f"{obj_label.title()} in {zone_label.title()}",
            "shortSummary": f"A {objects[0]} was seen in the {zones[0].replace('_', ' ')}.",
            "scene": f"A {obj_label} detected in {zone_label}.",
            "confidence": 0.92,
            "potential_threat_level": 1,
            "other_concerns": [],
            "time": now_dt,
        }
        genai_data = build_review_data(
            det_ids,
            objects,
            sub_labels,
            zones,
            thumb_time=thumb_time,
            metadata=genai_metadata,
        )
        publish(
            build_payload(
                "genai",
                review_id,
                args.camera,
                now,
                args.severity,
                args.severity,
                last_data,
                genai_data,
                end_time=end_time,
            ),
            "genai",
        )

    print("\nDone.")
    client.loop_stop()
    client.disconnect()


def main() -> None:
    """Parse CLI args and run the simulation."""
    parser = argparse.ArgumentParser(description="Simulate a Frigate review lifecycle via MQTT")
    parser.add_argument("--camera", default="driveway", help="Camera name (default: driveway)")
    parser.add_argument(
        "--objects", default="person,car", help="Comma-separated objects (default: person,car)"
    )
    parser.add_argument(
        "--zones",
        default="driveway_approach,driveway_main",
        help="Comma-separated zones (default: driveway_approach,driveway_main)",
    )
    parser.add_argument(
        "--sub-labels",
        default="",
        help="Comma-separated sub-labels, e.g. Bob (default: none)",
    )
    parser.add_argument(
        "--severity",
        default="alert",
        choices=["alert", "detection"],
        help="Target severity after escalation (default: alert)",
    )
    parser.add_argument("--delay", type=float, default=5.0, help="Seconds between phases")
    parser.add_argument("--no-genai", action="store_true", help="Skip genai phase")
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
