import os
import re
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse
from googleapiclient.discovery import build
from src.redact import redact_secrets


def get_youtube_client():
    """Builds and returns a YouTube Data API client."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "YOUTUBE_API_KEY environment variable is not set."
        )
    return build("youtube", "v3", developerKey=api_key)


def get_channel_uploads(
    channel_id: str, channel_name: str, tier: str, days_back: int = 7
) -> list[dict]:
    """
    Fetches uploads from a specific channel within the days_back limit.
    Handles pagination up to 3 pages.
    """
    youtube = get_youtube_client()
    try:
        # Retrieve the channel uploads playlist ID
        channel_response = (
            youtube.channels()
            .list(part="contentDetails", id=channel_id)
            .execute()
        )

        items = channel_response.get("items", [])
        if not items:
            print(f"Warning: Channel {channel_name} ({channel_id}) not found.")
            return []

        uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"][
            "uploads"
        ]
    except Exception as e:
        print(
            f"Warning: Failed to fetch channel details for {channel_name}: "
            f"{redact_secrets(str(e))}"
        )
        return []

    videos = []
    limit_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    next_page_token = None
    page_count = 0
    max_pages = 3

    try:
        while page_count < max_pages:
            playlist_response = (
                youtube.playlistItems()
                .list(
                    part="snippet",
                    playlistId=uploads_playlist_id,
                    maxResults=50,
                    pageToken=next_page_token,
                )
                .execute()
            )

            playlist_items = playlist_response.get("items", [])
            if not playlist_items:
                break

            for item in playlist_items:
                snippet = item.get("snippet", {})
                resource_id = snippet.get("resourceId", {})
                video_id = resource_id.get("videoId")
                published_at_str = snippet.get("publishedAt")

                if not video_id or not published_at_str:
                    continue

                published_at = isoparse(published_at_str)
                # Filter videos published within the window
                if published_at < limit_date:
                    continue

                videos.append(
                    {
                        "video_id": video_id,
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "published_at": published_at_str,
                        "tier": tier,
                    }
                )

            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break
            page_count += 1
    except Exception as e:
        print(
            f"Warning: Failed to retrieve videos for channel {channel_name}: "
            f"{redact_secrets(str(e))}"
        )

    return videos


def _duration_seconds(iso: str) -> int:
    """Seconds in an ISO 8601 duration like PT1H2M3S (days are not used by YouTube)."""
    match = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not match:
        return 0
    h, m, s = (int(x) if x else 0 for x in match.groups())
    return h * 3600 + m * 60 + s


def video_type(details: dict) -> str:
    """'live', 'short' (<= 3 min) or 'video' — the groups uploads are compared within."""
    if details.get("liveStreamingDetails"):
        return "live"
    seconds = _duration_seconds(details.get("contentDetails", {}).get("duration", ""))
    return "short" if 0 < seconds <= 180 else "video"


def get_video_details(video_ids: list[str]) -> dict[str, dict]:
    """
    Live public counts and type per video: {video_id: {"type", "duration_s",
    "views", "likes", "comments"}}. Counts are real time, unlike Analytics.
    """
    youtube = get_youtube_client()
    out = {}
    for i in range(0, len(video_ids), 50):
        response = (
            youtube.videos()
            .list(
                part="statistics,contentDetails,liveStreamingDetails",
                id=",".join(video_ids[i:i + 50]),
            )
            .execute()
        )
        for item in response.get("items", []):
            stats = item.get("statistics", {})
            out[item["id"]] = {
                "type": video_type(item),
                "duration_s": _duration_seconds(item.get("contentDetails", {}).get("duration", "")),
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
            }
    return out
