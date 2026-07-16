import json
import os

import requests

from src.redact import redact_secrets

GRAPH_BASE = "https://graph.facebook.com/v21.0"

MEDIA_FIELDS = (
    "id,caption,media_type,media_product_type,timestamp,permalink,"
    "like_count,comments_count"
)

# Insight metric sets per media_product_type. Meta deprecated `impressions`
# in favor of `views` (2025); metric availability varies by type, and
# fetch_media_insights degrades to {} if a set is rejected.
INSIGHT_METRICS = {
    "REELS": "reach,saved,shares,likes,comments,views,total_interactions",
    "FEED": "reach,saved,shares,views,total_interactions",
}


def _get(url: str, params: dict) -> dict:
    """Single Graph API GET with error unwrapping. Tests monkeypatch this."""
    response = requests.get(url, params=params, timeout=30)
    data = response.json()
    if "error" in data:
        raise RuntimeError(
            f"Instagram API error: {data['error'].get('message', 'unknown')}"
        )
    return data


def fetch_media(ig_user_id: str, token: str, limit: int = 100) -> list[dict]:
    """Fetches the most recent media objects (feed posts, carousels, reels)."""
    media = []
    url = f"{GRAPH_BASE}/{ig_user_id}/media"
    params = {"fields": MEDIA_FIELDS, "access_token": token, "limit": 50}
    while url and len(media) < limit:
        data = _get(url, params)
        page_items = data.get("data", [])
        if not page_items:
            break
        media.extend(page_items)
        url = data.get("paging", {}).get("next")
        params = {}  # the `next` URL already carries all query params
    return media[:limit]


def fetch_media_insights(media_id: str, token: str, media_product_type: str) -> dict:
    """Per-media insight metrics; returns {} if the API rejects the request."""
    metrics = INSIGHT_METRICS.get(media_product_type, INSIGHT_METRICS["FEED"])
    try:
        data = _get(
            f"{GRAPH_BASE}/{media_id}/insights",
            {"metric": metrics, "access_token": token},
        )
    except Exception as e:
        print(
            "Warning: insights fetch failed for media "
            f"{media_id}: {redact_secrets(str(e))}"
        )
        return {}
    out = {}
    for entry in data.get("data", []):
        values = entry.get("values") or [{}]
        out[entry.get("name")] = values[0].get("value", 0)
    return out


def fetch_media_comments(media_id: str, token: str, max_comments: int = 100) -> list[dict]:
    """Comments on a media object, capped. Returns [] on error."""
    comments = []
    url = f"{GRAPH_BASE}/{media_id}/comments"
    params = {
        "fields": "text,like_count,timestamp,username",
        "access_token": token,
        "limit": 50,
    }
    try:
        while url and len(comments) < max_comments:
            data = _get(url, params)
            page_items = data.get("data", [])
            if not page_items:
                break
            comments.extend(page_items)
            url = data.get("paging", {}).get("next")
            params = {}
    except Exception as e:
        print(
            "Warning: comment fetch failed for media "
            f"{media_id}: {redact_secrets(str(e))}"
        )
    return comments[:max_comments]


def _engagement(media_item: dict) -> int:
    return (media_item.get("like_count") or 0) + (media_item.get("comments_count") or 0)


def compute_movers(
    media: list[dict],
    snapshot: dict,
    recent_ids: set[str],
    min_delta: int = 20,
    ratio: float = 2.0,
    top_n: int = 5,
) -> list[dict]:
    """
    Back-catalog media with unusual engagement growth since the last snapshot:
    delta >= min_delta AND delta >= ratio x last week's delta. Media without a
    snapshot baseline (first sighting) are skipped — no way to know the delta.
    """
    old = snapshot.get("media", {})
    movers = []
    for m in media:
        media_id = m["id"]
        if media_id in recent_ids:
            continue
        baseline = old.get(media_id)
        if baseline is None or "engagement" not in baseline:
            continue
        delta = _engagement(m) - baseline["engagement"]
        prev_delta = baseline.get("delta", 0)
        if delta >= min_delta and delta >= ratio * max(prev_delta, 1):
            movers.append(
                {
                    "media_id": media_id,
                    "permalink": m.get("permalink"),
                    "delta_engagement": delta,
                    "prev_week_delta": prev_delta,
                }
            )
    movers.sort(key=lambda x: x["delta_engagement"], reverse=True)
    return movers[:top_n]


def build_snapshot(media: list[dict], old_snapshot: dict, run_date: str) -> dict:
    """New snapshot of lifetime engagement totals plus this week's delta."""
    old = old_snapshot.get("media", {})
    new_media = {}
    for m in media:
        engagement = _engagement(m)
        baseline = old.get(m["id"], {}).get("engagement")
        delta = engagement - baseline if baseline is not None else 0
        new_media[m["id"]] = {"engagement": engagement, "delta": delta}
    return {"snapshot_date": run_date, "media": new_media}


def load_snapshot(path: str) -> dict:
    if not os.path.exists(path):
        return {"media": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(path: str, snapshot: dict) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)


BUSINESS_DISCOVERY_MEDIA_FIELDS = (
    "caption,media_product_type,timestamp,permalink,like_count,comments_count"
)


def fetch_business_discovery(
    ig_user_id: str, token: str, username: str, media_limit: int = 25
) -> dict:
    """
    Public profile info and recent media of ANOTHER professional account,
    via the Business Discovery API. Raises on error (e.g. the target is
    not a Business/Creator account) — the collector isolates per-username.
    """
    fields = (
        f"business_discovery.username({username})"
        f"{{username,followers_count,media_count,"
        f"media.limit({media_limit}){{{BUSINESS_DISCOVERY_MEDIA_FIELDS}}}}}"
    )
    data = _get(
        f"{GRAPH_BASE}/{ig_user_id}",
        {"fields": fields, "access_token": token},
    )
    return data.get("business_discovery", {})
