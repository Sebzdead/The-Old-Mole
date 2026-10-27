#!/usr/bin/env python3
"""
Weekly data collector for The Old Mole media report.

Gathers our own YouTube and Instagram data: last week's uploads (with
live counts, comments and a same-type comparison), 26 weeks of
account-level history, and one trend chart per platform. Output goes to
trend-sensor/output/YYYY-MM-DD/; charts go to trend-sensor/digests/charts/.
Every source is isolated: a failure is recorded in run_meta.json statuses
and the remaining sources still run (partial-report policy).

The Claude routine (see ROUTINE.md) consumes the output bundle.
"""

import json
import math
import os
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dateutil.parser import isoparse
from dotenv import load_dotenv

from src import accounts, charts, fetcher, history, instagram, redact
from src import yt_analytics, yt_comments

load_dotenv(os.path.join(REPO_ROOT, ".env"))

OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "output")
CHARTS_ROOT = os.path.join(PROJECT_ROOT, "digests", "charts")
SNAPSHOT_PATH = os.path.join(PROJECT_ROOT, "state", "ig_snapshot.json")
FOLLOWERS_PATH = os.path.join(PROJECT_ROOT, "state", "ig_followers.json")
COMMENTS_PER_POST = 50
BASELINE_SIZE = 10  # earlier uploads of the same type each new one is compared with
UPLOAD_LOOKBACK_DAYS = 180
# YouTube Analytics reports days in Pacific time.
ANALYTICS_TZ = ZoneInfo("America/Los_Angeles")
IG_POST_METRICS = ("reach", "views", "likes", "comments", "shares", "saved")
MIN_AGE_TO_JUDGE_DAYS = 1  # younger uploads get no comparison: the numbers are noise


def reporting_windows(today: date, anchor_end: str | None = None) -> dict:
    """
    Both comparison windows are 7 days, ending at the last day analytics
    actually has data for.

    Passing anchor_end (from yt_analytics.latest_data_date) pins the window
    to real data availability. Without it we fall back to assuming a 48h
    lag, which under-reports the current week whenever the true lag is
    longer: the API silently returns a short window instead of an error, so
    a 6-day "this week" gets compared against a full 7-day "prev week".
    """
    this_end = date.fromisoformat(anchor_end) if anchor_end else today - timedelta(days=2)
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
        statuses[name] = {
            "ok": False,
            "error": redact.redact_secrets(f"{type(e).__name__}: {e}"),
        }
        return None


TOO_NEW = {"too_new_to_judge": True}


def _age_days(published_at: str, now: datetime) -> float:
    return round((now - isoparse(published_at)).total_seconds() / 86400, 1)


def _baseline_for(items: list[dict], kind_of, kind: str, size: int = BASELINE_SIZE) -> list[dict]:
    """The `size` most recent earlier items of the same kind (items are newest first)."""
    return [i for i in items if kind_of(i) == kind][:size]


def collect_own_youtube(own_channel_id: str, windows: dict, now: datetime) -> dict:
    data_client = fetcher.get_youtube_client()
    analytics_client = yt_analytics.get_analytics_client()
    last_day = date.fromisoformat(windows["this_end"])

    uploads = fetcher.get_channel_uploads(
        own_channel_id, "The Old Mole", tier="own", days_back=UPLOAD_LOOKBACK_DAYS
    )
    uploads.sort(key=lambda v: v["published_at"], reverse=True)
    cutoff = now - timedelta(days=7)
    recent = [v for v in uploads if isoparse(v["published_at"]) >= cutoff]
    earlier = [v for v in uploads if isoparse(v["published_at"]) < cutoff]

    details = fetcher.get_video_details([v["video_id"] for v in uploads])
    kind_of = lambda v: details.get(v["video_id"], {}).get("type")  # noqa: E731
    for v in uploads:
        v["type"] = kind_of(v)

    baselines = {
        kind: _baseline_for(earlier, kind_of, kind)
        for kind in {v["type"] for v in recent}
    }
    baseline_videos = [b for group in baselines.values() for b in group]
    baseline_ids = [b["video_id"] for b in baseline_videos]
    first_publish = min(
        (isoparse(v["published_at"]).astimezone(ANALYTICS_TZ).date() for v in recent + baseline_videos),
        default=last_day,
    )
    daily_views = yt_analytics.video_daily_views(
        analytics_client, baseline_ids, first_publish.isoformat(), last_day.isoformat()
    )
    baseline_metrics = yt_analytics.video_week_metrics(
        analytics_client, baseline_ids, first_publish.isoformat(), last_day.isoformat()
    )
    recent_ids = [v["video_id"] for v in recent]
    recent_metrics = {}
    if recent and first_publish <= last_day:
        recent_metrics = yt_analytics.video_week_metrics(
            analytics_client, recent_ids, first_publish.isoformat(), last_day.isoformat()
        )

    new_uploads = []
    for v in recent:
        live = details.get(v["video_id"], {})
        age = _age_days(v["published_at"], now)
        same_age_days = max(1, math.ceil(age))
        group = baselines.get(v["type"], [])
        views_then = [
            history.views_in_first_days(
                daily_views.get(b["video_id"], {}),
                isoparse(b["published_at"]).astimezone(ANALYTICS_TZ).date(),
                same_age_days,
            )
            for b in group
        ]
        pct_watched = [
            baseline_metrics.get(b["video_id"], {}).get("averageViewPercentage") for b in group
        ]
        analytics = recent_metrics.get(v["video_id"], {})
        new_uploads.append(
            {
                "video_id": v["video_id"],
                "url": f"https://www.youtube.com/watch?v={v['video_id']}",
                "title": v["title"],
                "published_at": v["published_at"],
                "age_days": age,
                "type": v["type"],
                "duration_s": live.get("duration_s"),
                "live_counts": {k: live.get(k) for k in ("views", "likes", "comments")},
                "finalized_analytics": {
                    "through": last_day.isoformat(),
                    "minutes_watched": analytics.get("estimatedMinutesWatched"),
                    "avg_pct_watched": analytics.get("averageViewPercentage"),
                    "subscribers_gained": analytics.get("subscribersGained"),
                    "shares": analytics.get("shares"),
                },
                "vs_typical": TOO_NEW if age < MIN_AGE_TO_JUDGE_DAYS else {
                    "compared_with": f"our last {len(group)} {v['type']} uploads",
                    "views_at_same_age": {
                        "days": same_age_days,
                        **history.compare_to_baseline(live.get("views"), views_then),
                    },
                    "avg_pct_watched": history.compare_to_baseline(
                        analytics.get("averageViewPercentage"), pct_watched
                    ),
                },
                "comments": yt_comments.fetch_comments(
                    data_client, v["video_id"], max_comments=COMMENTS_PER_POST
                ),
            }
        )

    week_windows = history.week_windows(last_day)
    daily = yt_analytics.channel_daily_metrics(
        analytics_client, week_windows[0]["start"], last_day.isoformat()
    )
    fields = ["views", "estimatedMinutesWatched", "likes", "comments",
              "subscribersGained", "subscribersLost"]
    weekly = history.bucket_daily(daily, week_windows, fields)
    subscribers = history.subscriber_totals(
        weekly, yt_analytics.lifetime_subscribers(analytics_client, last_day.isoformat())
    )
    for week, total in zip(weekly, subscribers):
        week["subscribers_total"] = total

    sources = yt_analytics.traffic_sources(
        analytics_client, windows["this_start"], windows["this_end"]
    )
    total_views = sum(sources.values()) or 1
    movers = yt_analytics.back_catalog_movers(
        analytics_client, set(recent_ids),
        windows["this_start"], windows["this_end"],
        windows["prev_start"], windows["prev_end"],
    )
    for m in movers:
        m["url"] = f"https://www.youtube.com/watch?v={m['video_id']}"

    this_week, prev_week = weekly[-1], weekly[-2]
    return {
        "new_uploads": new_uploads,
        "weekly_history": weekly,
        "this_week_vs_prev": {
            f: {"this": this_week[f], "prev": prev_week[f],
                "pct_change": history.pct_change(this_week[f], prev_week[f])}
            for f in fields + ["subscribers_total"]
        },
        "top_traffic_sources": [
            {"source": k, "views": n, "share_pct": round(n / total_views * 100)}
            for k, n in list(sources.items())[:3]
        ],
        "back_catalog_movers": movers,
    }


def _ig_numbers(post: dict) -> dict:
    insights = post.get("insights") or {}
    return {
        "reach": insights.get("reach"),
        "views": insights.get("views"),
        "likes": post.get("like_count"),
        "comments": post.get("comments_count"),
        "shares": insights.get("shares"),
        "saved": insights.get("saved"),
    }


def collect_instagram(ig_user_id: str, run_date: str, now: datetime) -> dict:
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("IG_ACCESS_TOKEN environment variable is not set.")

    media = instagram.fetch_media(ig_user_id, token, limit=100)
    media.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
    cutoff = now - timedelta(days=7)
    recent = [m for m in media if m.get("timestamp") and isoparse(m["timestamp"]) >= cutoff]
    earlier = [m for m in media if m.get("timestamp") and isoparse(m["timestamp"]) < cutoff]
    kind_of = lambda m: m.get("media_product_type", "FEED")  # noqa: E731

    baselines = {}
    for kind in {kind_of(m) for m in recent}:
        group = _baseline_for(earlier, kind_of, kind)
        for m in group:
            m["insights"] = instagram.fetch_media_insights(m["id"], token, kind)
        baselines[kind] = [_ig_numbers(m) for m in group]

    new_posts = []
    for m in recent:
        m["insights"] = instagram.fetch_media_insights(m["id"], token, kind_of(m))
        numbers = _ig_numbers(m)
        age = _age_days(m["timestamp"], now)
        group = baselines.get(kind_of(m), [])
        new_posts.append(
            {
                "id": m["id"],
                "permalink": m.get("permalink"),
                "caption": m.get("caption", ""),
                "type": kind_of(m),
                "media_type": m.get("media_type"),
                "published_at": m["timestamp"],
                "age_days": age,
                "numbers": numbers,
                "vs_typical": TOO_NEW if age < MIN_AGE_TO_JUDGE_DAYS else {
                    "compared_with": f"lifetime totals of our last {len(group)} {kind_of(m)} posts",
                    **{
                        k: history.compare_to_baseline(numbers[k], [b[k] for b in group])
                        for k in IG_POST_METRICS
                    },
                },
                "comments": instagram.fetch_media_comments(
                    m["id"], token, max_comments=COMMENTS_PER_POST
                ),
            }
        )

    old_snapshot = instagram.load_snapshot(SNAPSHOT_PATH)
    movers = instagram.compute_movers(media, old_snapshot, {m["id"] for m in recent})
    instagram.save_snapshot(SNAPSHOT_PATH, instagram.build_snapshot(media, old_snapshot, run_date))

    last_day = instagram.last_complete_day(now)
    week_windows = history.week_windows(last_day)
    weekly = []
    for w in week_windows:
        totals = instagram.fetch_account_week(
            ig_user_id, token, date.fromisoformat(w["start"]), date.fromisoformat(w["end"])
        )
        weekly.append({**w, **totals})

    followers_now = instagram.fetch_followers(ig_user_id, token)
    snapshots = history.load_followers(FOLLOWERS_PATH)
    snapshots[run_date] = followers_now
    history.save_followers(FOLLOWERS_PATH, snapshots)
    gains = instagram.fetch_daily_follower_gains(ig_user_id, token, now.date())
    followers = history.follower_series(week_windows, snapshots, followers_now, gains)
    for week, f in zip(weekly, followers):
        week["followers"] = f["followers"]
        week["followers_estimated"] = f["estimated"]

    this_week, prev_week = weekly[-1], weekly[-2]
    return {
        "new_posts": new_posts,
        "weekly_history": weekly,
        "followers_now": followers_now,
        "follower_tracking_since": min(snapshots),
        "this_week_vs_prev": {
            f: {"this": this_week.get(f), "prev": prev_week.get(f),
                "pct_change": history.pct_change(this_week.get(f), prev_week.get(f))}
            for f in ("reach", "views", "total_interactions", "followers")
        },
        "back_catalog_movers": movers,
    }


def write_json(out_dir: str, name: str, payload: dict) -> None:
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def resolve_anchor_end(today: date) -> str | None:
    """Last day with analytics data, or None if the probe fails."""
    try:
        return yt_analytics.latest_data_date(
            yt_analytics.get_analytics_client(), today
        )
    except Exception as e:
        print(
            "Warning: could not probe analytics data availability, falling "
            f"back to a fixed 48h lag: {redact.redact_secrets(str(e))}"
        )
        return None


def main():
    now = datetime.now(timezone.utc)
    today = date.today()
    run_date = today.isoformat()
    anchor_end = resolve_anchor_end(today)
    windows = reporting_windows(today, anchor_end)
    out_dir = os.path.join(OUTPUT_ROOT, run_date)
    chart_dir = os.path.join(CHARTS_ROOT, run_date)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(chart_dir, exist_ok=True)

    statuses = {}
    account_config = run_source(statuses, "accounts_config", accounts.load_accounts)

    youtube = instagram_data = None
    if account_config:
        youtube = run_source(
            statuses, "youtube",
            lambda: collect_own_youtube(account_config["own_youtube_channel_id"], windows, now),
        )
        instagram_data = run_source(
            statuses, "instagram",
            lambda: collect_instagram(account_config["instagram_user_id"], run_date, now),
        )
    else:
        statuses["youtube"] = {"ok": False, "error": "accounts_config failed"}
        statuses["instagram"] = {"ok": False, "error": "accounts_config failed"}

    chart_files = {}
    if youtube:
        write_json(out_dir, "youtube.json", youtube)
        path = os.path.join(chart_dir, "youtube.png")
        if run_source(statuses, "youtube_chart", lambda: charts.youtube_chart(
            youtube["weekly_history"],
            [w["subscribers_total"] for w in youtube["weekly_history"]],
            path,
        )):
            chart_files["youtube"] = f"charts/{run_date}/youtube.png"
    if instagram_data:
        write_json(out_dir, "instagram.json", instagram_data)
        path = os.path.join(chart_dir, "instagram.png")
        followers = [
            {"followers": w["followers"], "estimated": w["followers_estimated"]}
            for w in instagram_data["weekly_history"]
        ]
        if run_source(statuses, "instagram_chart", lambda: charts.instagram_chart(
            instagram_data["weekly_history"], followers, path,
        )):
            chart_files["instagram"] = f"charts/{run_date}/instagram.png"

    run_meta = {
        "run_date": run_date,
        "youtube_week": {"start": windows["this_start"], "end": windows["this_end"]},
        "instagram_week": (
            {k: instagram_data["weekly_history"][-1][k] for k in ("start", "end")}
            if instagram_data else None
        ),
        "analytics_last_data_date": anchor_end,
        "analytics_lag_days": (
            (today - date.fromisoformat(anchor_end)).days if anchor_end else None
        ),
        "charts": chart_files,
        "statuses": statuses,
        "output_dir": out_dir,
    }
    write_json(out_dir, "run_meta.json", run_meta)

    print(json.dumps(run_meta, indent=2))
    failed = [name for name, s in statuses.items() if not s["ok"]]
    if failed:
        print(f"Completed with failed sources: {', '.join(failed)}", file=sys.stderr)
    else:
        print("All sources collected successfully.")


if __name__ == "__main__":
    main()
