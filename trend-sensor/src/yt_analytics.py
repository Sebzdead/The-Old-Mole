import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_URI = "https://oauth2.googleapis.com/token"

CHANNEL_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,likes,comments,"
    "shares,subscribersGained,subscribersLost"
)
VIDEO_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,"
    "averageViewPercentage,likes,comments,shares"
)


def get_analytics_client():
    """Builds a YouTube Analytics API v2 client from OAuth refresh-token env vars."""
    client_id = os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_CLIENT_SECRET")
    refresh_token = os.environ.get("YT_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        raise RuntimeError(
            "YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN must all be set."
        )
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
    )
    return build("youtubeAnalytics", "v2", credentials=creds)


def _rows_as_dicts(response: dict) -> list[dict]:
    headers = [h["name"] for h in response.get("columnHeaders", [])]
    return [dict(zip(headers, row)) for row in response.get("rows", []) or []]


def channel_week_metrics(client, start_date: str, end_date: str) -> dict:
    """Channel-wide totals for the window."""
    response = (
        client.reports()
        .query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics=CHANNEL_METRICS,
        )
        .execute()
    )
    rows = _rows_as_dicts(response)
    return rows[0] if rows else {}


def video_week_metrics(
    client, video_ids: list[str], start_date: str, end_date: str
) -> dict:
    """Per-video metrics for the given videos, keyed by video ID."""
    if not video_ids:
        return {}
    response = (
        client.reports()
        .query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics=VIDEO_METRICS,
            dimensions="video",
            filters="video==" + ",".join(video_ids),
            maxResults=200,
        )
        .execute()
    )
    out = {}
    for row in _rows_as_dicts(response):
        video_id = row.pop("video")
        out[video_id] = row
    return out


def traffic_sources(client, start_date: str, end_date: str) -> dict:
    """Views by traffic source type for the window."""
    response = (
        client.reports()
        .query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="insightTrafficSourceType",
            sort="-views",
        )
        .execute()
    )
    return {row[0]: row[1] for row in response.get("rows", []) or []}


def _top_videos_by_views(client, start_date: str, end_date: str) -> dict:
    response = (
        client.reports()
        .query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="video",
            sort="-views",
            maxResults=200,
        )
        .execute()
    )
    return {row[0]: row[1] for row in response.get("rows", []) or []}


def back_catalog_movers(
    client,
    recent_video_ids: set[str],
    this_start: str,
    this_end: str,
    prev_start: str,
    prev_end: str,
    min_views: int = 200,
    ratio: float = 2.0,
    top_n: int = 5,
) -> list[dict]:
    """
    Older videos (not in recent_video_ids) with unusual activity this week:
    at least min_views this window AND at least ratio x last window's views.
    """
    this_week = _top_videos_by_views(client, this_start, this_end)
    prev_week = _top_videos_by_views(client, prev_start, prev_end)
    movers = []
    for video_id, views in this_week.items():
        if video_id in recent_video_ids:
            continue
        prev = prev_week.get(video_id, 0)
        if views >= min_views and views >= ratio * max(prev, 1):
            movers.append(
                {
                    "video_id": video_id,
                    "views_this_week": views,
                    "views_prev_week": prev,
                }
            )
    movers.sort(key=lambda m: m["views_this_week"], reverse=True)
    return movers[:top_n]
