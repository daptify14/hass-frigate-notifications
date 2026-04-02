"""Canonical MQTT payload constants for processor tests.

These represent the exact shapes Frigate sends on the reviews topic.
All payloads use consistent review_id and camera for lifecycle chaining.
"""

REVIEW_NEW_PAYLOAD: dict = {
    "type": "new",
    "before": {
        "id": "1773840946.10543-review1",
        "camera": "driveway",
        "start_time": 1773840946.10543,
        "end_time": None,
        "severity": "alert",
        "data": {
            "detections": [],
            "objects": [],
            "sub_labels": [],
            "zones": [],
            "audio": [],
            "metadata": None,
        },
    },
    "after": {
        "id": "1773840946.10543-review1",
        "camera": "driveway",
        "start_time": 1773840946.10543,
        "end_time": None,
        "severity": "alert",
        "data": {
            "detections": ["det_id_1"],
            "objects": ["person"],
            "sub_labels": [],
            "zones": ["driveway_approach"],
            "audio": [],
            "metadata": None,
        },
    },
}

REVIEW_UPDATE_PAYLOAD: dict = {
    "type": "update",
    "before": {
        "id": "1773840946.10543-review1",
        "camera": "driveway",
        "start_time": 1773840946.10543,
        "end_time": None,
        "severity": "alert",
        "data": {
            "detections": ["det_id_1"],
            "objects": ["person"],
            "sub_labels": [],
            "zones": ["driveway_approach"],
            "audio": [],
            "metadata": None,
        },
    },
    "after": {
        "id": "1773840946.10543-review1",
        "camera": "driveway",
        "start_time": 1773840946.10543,
        "end_time": None,
        "severity": "alert",
        "data": {
            "detections": ["det_id_1", "det_id_2"],
            "objects": ["person", "car"],
            "sub_labels": [],
            "zones": ["driveway_approach", "driveway_main"],
            "audio": [],
            "metadata": None,
        },
    },
}

REVIEW_END_PAYLOAD: dict = {
    "type": "end",
    "before": {
        "id": "1773840946.10543-review1",
        "camera": "driveway",
        "start_time": 1773840946.10543,
        "end_time": None,
        "severity": "alert",
        "data": {
            "detections": ["det_id_1", "det_id_2"],
            "objects": ["person", "car"],
            "sub_labels": [],
            "zones": ["driveway_approach", "driveway_main"],
            "audio": [],
            "metadata": None,
        },
    },
    "after": {
        "id": "1773840946.10543-review1",
        "camera": "driveway",
        "start_time": 1773840946.10543,
        "end_time": 1773840991.854811,
        "severity": "alert",
        "data": {
            "detections": ["det_id_1", "det_id_2"],
            "objects": ["person", "car"],
            "sub_labels": [],
            "zones": ["driveway_approach", "driveway_main"],
            "audio": [],
            "metadata": None,
        },
    },
}

REVIEW_GENAI_PAYLOAD: dict = {
    "type": "genai",
    "before": {
        "id": "1773840946.10543-review1",
        "camera": "driveway",
        "start_time": 1773840946.10543,
        "end_time": 1773840991.854811,
        "severity": "alert",
        "data": {
            "detections": ["det_id_1", "det_id_2"],
            "objects": ["person", "car"],
            "sub_labels": [],
            "zones": ["driveway_approach", "driveway_main"],
            "audio": [],
            "metadata": None,
        },
    },
    "after": {
        "id": "1773840946.10543-review1",
        "camera": "driveway",
        "start_time": 1773840946.10543,
        "end_time": 1773840991.854811,
        "severity": "alert",
        "data": {
            "detections": ["det_id_1", "det_id_2"],
            "objects": ["person", "car"],
            "sub_labels": [],
            "zones": ["driveway_approach", "driveway_main"],
            "audio": [],
            "metadata": {
                "title": "Person and Vehicle in Driveway",
                "shortSummary": "A person walked up the driveway as a car pulled in.",
                "scene": "A person walks up the driveway approach as a car enters.",
                "confidence": 0.92,
                "potential_threat_level": 1,
                "other_concerns": ["Vehicle speed appears normal"],
                "time": "Wednesday, 09:35 AM",
            },
        },
    },
}
