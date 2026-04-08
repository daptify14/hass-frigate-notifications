"""URL templates, content types, and media validation constants."""

from .enums import AttachmentType, VideoType

_NOTIFY_BASE = "{{ base_url }}/api/frigate{{ client_id }}/notifications"
_DETECTION_ID = "{{ detection_id }}"
_REVIEW_ID = "{{ review_id }}"
_CAMERA = "{{ camera }}"

ATTACHMENT_URL_TEMPLATES: dict[str, str] = {
    "thumbnail": f"{_NOTIFY_BASE}/{_DETECTION_ID}/thumbnail.jpg",
    "snapshot": f"{_NOTIFY_BASE}/{_DETECTION_ID}/snapshot.jpg?bbox=0&crop=0",
    "snapshot_bbox": f"{_NOTIFY_BASE}/{_DETECTION_ID}/snapshot.jpg?bbox=1&crop=0",
    "snapshot_cropped": f"{_NOTIFY_BASE}/{_DETECTION_ID}/snapshot.jpg?bbox=0&crop=1",
    "snapshot_cropped_bbox": f"{_NOTIFY_BASE}/{_DETECTION_ID}/snapshot.jpg?bbox=1&crop=1",
    "review_gif": f"{_NOTIFY_BASE}/{_REVIEW_ID}/review_preview.gif",
    "event_gif": f"{_NOTIFY_BASE}/{_DETECTION_ID}/event_preview.gif",
}

VIDEO_URL_TEMPLATES: dict[str, str] = {
    VideoType.REVIEW_GIF_VIDEO: f"{_NOTIFY_BASE}/{_REVIEW_ID}/review_preview.gif?format=mp4",
    VideoType.CLIP_MP4: f"{_NOTIFY_BASE}/{_DETECTION_ID}/{_CAMERA}/clip.mp4",
    VideoType.CLIP_HLS: f"{_NOTIFY_BASE}/{_DETECTION_ID}/{_CAMERA}/master.m3u8",
}

ANDROID_IMAGE_URL_TEMPLATES: dict[str, str] = {
    "thumbnail": f"{_NOTIFY_BASE}/{_DETECTION_ID}/thumbnail.jpg?format=android",
    "snapshot": f"{_NOTIFY_BASE}/{_DETECTION_ID}/snapshot.jpg?bbox=0&crop=0&format=android",
    "snapshot_bbox": f"{_NOTIFY_BASE}/{_DETECTION_ID}/snapshot.jpg?bbox=1&crop=0&format=android",
    "snapshot_cropped": f"{_NOTIFY_BASE}/{_DETECTION_ID}/snapshot.jpg?bbox=0&crop=1&format=android",
    "snapshot_cropped_bbox": (
        f"{_NOTIFY_BASE}/{_DETECTION_ID}/snapshot.jpg?bbox=1&crop=1&format=android"
    ),
    "review_gif": f"{_NOTIFY_BASE}/{_REVIEW_ID}/review_preview.gif",
    "event_gif": f"{_NOTIFY_BASE}/{_DETECTION_ID}/event_preview.gif",
}

ATTACHMENT_CONTENT_TYPES: dict[str, str] = {
    "thumbnail": "jpeg",
    "snapshot": "jpeg",
    "snapshot_bbox": "jpeg",
    "snapshot_cropped": "jpeg",
    "snapshot_cropped_bbox": "jpeg",
    "review_gif": "gif",
    "event_gif": "gif",
}

VIDEO_CONTENT_TYPES: dict[str, str] = {
    VideoType.REVIEW_GIF_VIDEO: "mp4",
    VideoType.CLIP_MP4: "mp4",
    VideoType.CLIP_HLS: "application/vnd.apple.mpegurl",
}

# Android video: mp4 only (HLS falls back to mp4).
ANDROID_VIDEO_URL_TEMPLATES: dict[str, str] = {
    VideoType.REVIEW_GIF_VIDEO: f"{_NOTIFY_BASE}/{_REVIEW_ID}/review_preview.gif?format=mp4",
    VideoType.CLIP_MP4: f"{_NOTIFY_BASE}/{_DETECTION_ID}/{_CAMERA}/clip.mp4",
    VideoType.CLIP_HLS: f"{_NOTIFY_BASE}/{_DETECTION_ID}/{_CAMERA}/clip.mp4",  # Fallback to mp4.
}

DEFAULT_SNAPSHOT_URL = ATTACHMENT_URL_TEMPLATES["snapshot_cropped"]
DEFAULT_GIF_URL = ATTACHMENT_URL_TEMPLATES["review_gif"]

VALID_ATTACHMENTS = [m.value for m in AttachmentType]
VALID_TV_ATTACHMENTS = [
    m.value
    for m in AttachmentType
    if m not in (AttachmentType.REVIEW_GIF, AttachmentType.EVENT_GIF)
]
VALID_VIDEOS = (
    VideoType.CLIP_HLS,
    VideoType.CLIP_MP4,
    VideoType.LIVE_VIEW,
    VideoType.NONE,
    VideoType.REVIEW_GIF_VIDEO,
)
VALID_VIDEOS_NO_HLS = (VideoType.CLIP_MP4, VideoType.NONE, VideoType.REVIEW_GIF_VIDEO)
