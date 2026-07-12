#!/usr/bin/env python3
"""
Weekly data collector for The Old Mole intelligence report.

Gathers competitor transcripts, own-channel YouTube analytics + comments,
and Instagram insights + comments into trend-sensor/output/YYYY-MM-DD/.
Every source is isolated: a failure is recorded in run_meta.json statuses
and the remaining sources still run (partial-report policy).

The Claude routine (see ROUTINE.md) consumes the output bundle.
"""

import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta, timezone

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import yaml
from dateutil.parser import isoparse
from dotenv import load_dotenv

from src import accounts, cache, corpus, fetcher, instagram, transcripts
from src import yt_analytics, yt_comments

load_dotenv(os.path.join(REPO_ROOT, ".env"))

OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "output")
SNAPSHOT_PATH = os.path.join(PROJECT_ROOT, "state", "ig_snapshot.json")
COMMENTS_PER_POST = 100


def reporting_windows(today: date) -> dict:
    """
    Analytics data lags ~48h, so the report window is today-8 .. today-2,
    with the preceding 7 days as the comparison window for movers.
    """
    this_end = today - timedelta(days=2)
    this_start = this_end - timedelta(days=6)
    prev_end = this_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    return {
        "this_start": this_start.isoformat(),
        "this_end": this_end.isoformat(),
        "prev_start": prev_start.isoformat(),
        "prev_end": prev_end.isoformat(),
    }


def run_source(statuses: dict, name: str, fn):
    """Runs one source, recording ok/error. Returns fn() or None on failure."""
    try:
        result = fn()
        statuses[name] = {"ok": True, "error": None}
        return result
    except Exception as e:
        traceback.print_exc()
        statuses[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return None


def collect_competitors(out_dir: str) -> None:
    config_path = os.path.join(PROJECT_ROOT, "config", "channels.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        channels = yaml.safe_load(f).get("channels", [])
    cache.init_db()
    new_videos = fetcher.fetch_all_channels(channels, days_back=7)
    for video in new_videos:
        cache.save_video(video)
    transcripts.fetch_transcripts_for_corpus(new_videos)
    weekly_corpus = cache.get_corpus_since(days=7)
    formatted = corpus.format_corpus(weekly_corpus)
    meta = {
        "video_count": len(weekly_corpus),
        "channel_count": len({v["channel_name"] for v in weekly_corpus}),
    }
    with open(os.path.join(out_dir, "competitor_corpus.md"), "w", encoding="utf-8") as f:
        f.write(formatted)
    with open(os.path.join(out_dir, "competitor_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def collect_own_youtube(out_dir: str, own_channel_id: str, windows: dict) -> None:
    data_client = fetcher.get_youtube_client()
    analytics_client = yt_analytics.get_analytics_client()

    uploads = fetcher.get_channel_uploads(
        own_channel_id, "The Old Mole", tier="own", days_back=7
    )
    recent_ids = {v["video_id"] for v in uploads}

    per_video = yt_analytics.video_week_metrics(
        analytics_client, sorted(recent_ids), windows["this_start"], windows["this_end"]
    )
    for video in uploads:
        video["metrics"] = per_video.get(video["video_id"], {})
        video["comments"] = yt_comments.fetch_comments(
            data_client, video["video_id"], max_comments=COMMENTS_PER_POST
        )

    movers = yt_analytics.back_catalog_movers(
        analytics_client,
        recent_ids,
        windows["this_start"],
        windows["this_end"],
        windows["prev_start"],
        windows["prev_end"],
    )

    payload = {
        "channel_week": yt_analytics.channel_week_metrics(
            analytics_client, windows["this_start"], windows["this_end"]
        ),
        "channel_prev_week": yt_analytics.channel_week_metrics(
            analytics_client, windows["prev_start"], windows["prev_end"]
        ),
        "traffic_sources": yt_analytics.traffic_sources(
            analytics_client, windows["this_start"], windows["this_end"]
        ),
        "recent_uploads": uploads,
        "back_catalog_movers": movers,
    }
    with open(os.path.join(out_dir, "own_youtube.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def collect_instagram(out_dir: str, ig_user_id: str, run_date: str) -> None:
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("IG_ACCESS_TOKEN environment variable is not set.")

    media = instagram.fetch_media(ig_user_id, token, limit=100)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = [
        m for m in media
        if m.get("timestamp") and isoparse(m["timestamp"]) >= cutoff
    ]
    recent_ids = {m["id"] for m in recent}

    for m in recent:
        m["insights"] = instagram.fetch_media_insights(
            m["id"], token, m.get("media_product_type", "FEED")
        )
        m["comments"] = instagram.fetch_media_comments(
            m["id"], token, max_comments=COMMENTS_PER_POST
        )

    old_snapshot = instagram.load_snapshot(SNAPSHOT_PATH)
    movers = instagram.compute_movers(media, old_snapshot, recent_ids)
    permalinks = {m["id"]: m.get("permalink") for m in media}
    new_snapshot = instagram.build_snapshot(media, old_snapshot, run_date)
    instagram.save_snapshot(SNAPSHOT_PATH, new_snapshot)

    payload = {
        "recent_posts": recent,
        "back_catalog_movers": movers,
        "permalinks": permalinks,
        "previous_snapshot_date": old_snapshot.get("snapshot_date"),
    }
    with open(os.path.join(out_dir, "instagram.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main():
    run_date = date.today().isoformat()
    windows = reporting_windows(date.today())
    out_dir = os.path.join(OUTPUT_ROOT, run_date)
    os.makedirs(out_dir, exist_ok=True)

    statuses = {}

    account_config = run_source(statuses, "accounts_config", accounts.load_accounts)

    run_source(statuses, "competitors", lambda: collect_competitors(out_dir))

    if account_config:
        run_source(
            statuses,
            "own_youtube",
            lambda: collect_own_youtube(
                out_dir, account_config["own_youtube_channel_id"], windows
            ),
        )
        run_source(
            statuses,
            "instagram",
            lambda: collect_instagram(
                out_dir, account_config["instagram_user_id"], run_date
            ),
        )
    else:
        statuses["own_youtube"] = {"ok": False, "error": "accounts_config failed"}
        statuses["instagram"] = {"ok": False, "error": "accounts_config failed"}

    run_meta = {
        "run_date": run_date,
        "windows": windows,
        "statuses": statuses,
        "output_dir": out_dir,
    }
    with open(os.path.join(out_dir, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump(run_meta, f, indent=2)

    print(json.dumps(run_meta, indent=2))
    failed = [name for name, s in statuses.items() if not s["ok"]]
    if failed:
        print(f"Completed with failed sources: {', '.join(failed)}", file=sys.stderr)
    else:
        print("All sources collected successfully.")


if __name__ == "__main__":
    main()
