"""Constants for Notifications for Frigate."""

DOMAIN = "frigate_notifications"
FRIGATE_DOMAIN = "frigate"

SUBENTRY_TYPE_PROFILE = "profile"
SUBENTRY_TYPE_INTEGRATION = "integration"

SIGNAL_DISPATCH_PROBLEM = f"{DOMAIN}_dispatch_problem"
SIGNAL_LAST_SENT = f"{DOMAIN}_last_sent"
SIGNAL_SILENCE_STATE = f"{DOMAIN}_silence_state"
SIGNAL_STATS = f"{DOMAIN}_stats"

TOPIC_SUFFIX_REVIEWS = "reviews"

DEFAULT_TITLE_TEMPLATE = "camera_time"
DEFAULT_MESSAGE_TEMPLATE = "object_action_zone"
DEFAULT_TAG = "{{ review_id }}"
DEFAULT_GROUP = "{{ camera }}-frigate-notification"
DEFAULT_EMOJI = "\U0001f514"  # bell
DEFAULT_TITLE_GENAI_PREFIXES: dict[int, str] = {1: "\u26a1", 2: "\u26a0\ufe0f"}

DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_COOLDOWN_SECONDS = 0

STALE_REVIEW_TIMEOUT = 1800  # 30 minutes.
CLEANUP_INTERVAL = 300  # 5 minutes.
MAX_PAYLOAD_SIZE = 65536  # 64 KB.
MAX_DETECTION_IDS = 50

GUARD_ENTITY_DOMAINS = ("input_boolean", "switch", "binary_sensor")

PRESENCE_ENTITY_DOMAINS = ("device_tracker", "person", "group")


def humanize_zone(zone: str) -> str:
    """Convert a snake_case zone name to a human-readable label."""
    return zone.replace("_", " ").title()


def format_camera_text(cameras: list[str] | tuple[str, ...]) -> str:
    """Format a camera list into compact display text.

    Assumes cameras are already in canonical (alphabetical) order.
    """
    if not cameras:
        return ""
    count = len(cameras)
    if count <= 1:
        return humanize_zone(cameras[0])
    names = [humanize_zone(c) for c in cameras]
    if count == 2:  # Two cameras: show both inline  # noqa: PLR2004
        return f"{names[0]}, {names[1]}"
    return f"{names[0]} +{count - 1}"


DEFAULT_EMOJI_MAP: dict[str, str] = {
    # People
    "person": "\U0001f464",
    # Vehicles
    "car": "\U0001f698",
    "motorcycle": "\U0001f3cd\ufe0f",
    "bicycle": "\U0001f6b2",
    "bus": "\U0001f68c",
    "school_bus": "\U0001f68c",
    "boat": "\U0001f6a2",
    "airplane": "\u2708\ufe0f",
    "train": "\U0001f686",
    # Animals
    "dog": "\U0001f415",
    "cat": "\U0001f408",
    "bird": "\U0001f426",
    "horse": "\U0001f434",
    "deer": "\U0001f98c",
    "bear": "\U0001f43b",
    "raccoon": "\U0001f99d",
    "fox": "\U0001f98a",
    "squirrel": "\U0001f43f\ufe0f",
    "rabbit": "\U0001f407",
    "cow": "\U0001f404",
    "sheep": "\U0001f411",
    "goat": "\U0001f410",
    "skunk": "\U0001f9a8",
    # Delivery
    "package": "\U0001f4e6",
    "amazon": "\U0001f4e6",
    "usps": "\U0001f4ec",
    "ups": "\U0001f4e4",
    "fedex": "\U0001f4eb",
    "dhl": "\U0001f4ee",
    "royal_mail": "\U0001f4ee",
    "canada_post": "\U0001f4ec",
    # Objects
    "umbrella": "\u2602\ufe0f",
    "backpack": "\U0001f392",
    "suitcase": "\U0001f9f3",
    "sports ball": "\u26bd",
    "skateboard": "\U0001f6f9",
    "surfboard": "\U0001f3c4",
    "teddy bear": "\U0001f9f8",
    "waste_bin": "\U0001f5d1\ufe0f",
    "robot_lawnmower": "\U0001f916",
}

DEFAULT_PHASE_EMOJI_MAP: dict[str, str] = {
    "initial": "\U0001f195",  # 🆕
    "update": "\U0001f504",  # 🔄
    "end": "\U0001f51a",  # 🔚
    "genai": "\u2728",  # ✨
}
