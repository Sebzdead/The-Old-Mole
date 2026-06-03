import os
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse
from googleapiclient.discovery import build
from src.cache import is_video_cached


def get_youtube_client():
    """Builds and returns a YouTube Data API client."""
    api_key = os.environ.get(
        "YOUTUBE_API_KEY", "AIzaSyBbifKeM6QnAPsxYu2x1doQMhuy-RRDYTM"
    )
    if api_key == "AIzaSyBbifKeM6QnAPsxYu2x1doQMhuy-RRDYTM":
        print("Using default fallback YouTube API Key.")
    else:
        print("Using YouTube API Key from environment.")
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
            f"Warning: Failed to fetch channel details for {channel_name}: {e}"
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
            f"Warning: Failed to retrieve videos for channel {channel_name}: {e}"
        )

    return videos


def fetch_all_channels(
    channels: list[dict], days_back: int = 7
) -> list[dict]:
    """
    Iterates over channels config list, fetches recent videos, and filters
    out already-cached videos.
    """
    new_videos = []
    for ch in channels:
        channel_id = ch["id"]
        channel_name = ch["name"]
        tier = ch.get("tier", "broad")

        print(f"Fetching {channel_name}...")
        fetched = get_channel_uploads(
            channel_id, channel_name, tier, days_back
        )

        channel_new_count = 0
        for vid in fetched:
            if not is_video_cached(vid["video_id"]):
                new_videos.append(vid)
                channel_new_count += 1

        print(f"Fetcher: {channel_name}... {channel_new_count} new videos found")

    return new_videos
