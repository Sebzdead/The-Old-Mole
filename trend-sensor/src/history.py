"""
Pure helpers for the weekly trend history and same-age upload comparisons.
No API calls here — the collector fetches, these functions shape.
"""

import json
import os
from datetime import date, timedelta
from statistics import median

WEEKS = 26


def week_windows(last_day: date, weeks: int = WEEKS) -> list[dict]:
    """
    Consecutive 7-day windows ending on last_day, oldest first.
    Each window is {"start": iso, "end": iso}.
    """
    windows = []
    for k in range(weeks - 1, -1, -1):
        end = last_day - timedelta(days=7 * k)
        windows.append(
            {"start": (end - timedelta(days=6)).isoformat(), "end": end.isoformat()}
        )
    return windows


def bucket_daily(daily_rows: list[dict], windows: list[dict], fields: list[str]) -> list[dict]:
    """
    Sums daily rows ({"day": iso, field: n, ...}) into the given windows.
    Returns one dict per window: {"start", "end", field: total, ...}.
    """
    out = []
    for w in windows:
        totals = {f: 0 for f in fields}
        for row in daily_rows:
            if w["start"] <= row["day"] <= w["end"]:
                for f in fields:
                    totals[f] += row.get(f) or 0
        out.append({"start": w["start"], "end": w["end"], **totals})
    return out


def subscriber_totals(weekly: list[dict], total_at_last_day: int) -> list[int]:
    """
    Running subscriber count at the end of each week, back-calculated from
    the exact total on the last day (YouTube Analytics lifetime gained -
    lost) by undoing each later week's net change.
    """
    totals = []
    running = total_at_last_day
    for week in reversed(weekly):
        totals.append(running)
        running -= (week.get("subscribersGained") or 0) - (week.get("subscribersLost") or 0)
    return list(reversed(totals))


def pct_change(this: float | None, prev: float | None) -> float | None:
    """Percent change, or None when there is no meaningful baseline."""
    if this is None or not prev:
        return None
    return round((this - prev) / prev * 100, 1)


def views_in_first_days(daily_views: dict[str, int], published: date, days: int) -> int:
    """Views a video earned on its first `days` calendar days (publish day = day 1)."""
    last = published + timedelta(days=days - 1)
    return sum(v for d, v in daily_views.items() if published.isoformat() <= d <= last.isoformat())


def compare_to_baseline(value: float | None, baseline_values: list[float], min_baseline: int = 3) -> dict:
    """
    How `value` compares with the median of `baseline_values`.
    Returns {"median", "ratio", "baseline_n"}; ratio is None when the
    baseline is too small to mean anything.
    """
    values = [v for v in baseline_values if v is not None]
    if value is None or len(values) < min_baseline:
        return {"median": None, "ratio": None, "baseline_n": len(values)}
    mid = median(values)
    return {
        "median": mid,
        "ratio": round(value / mid, 2) if mid else None,
        "baseline_n": len(values),
    }


def load_followers(path: str) -> dict:
    """Weekly Instagram follower snapshots: {"YYYY-MM-DD": count}."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_followers(path: str, snapshots: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(snapshots.items())), f, indent=2)
        f.write("\n")


def follower_series(
    windows: list[dict],
    snapshots: dict,
    current: int,
    daily_gains: dict[str, int],
    tolerance_days: int = 3,
) -> list[dict]:
    """
    Follower count at the end of each window, oldest first.

    A saved snapshot within `tolerance_days` after a window's end is used as
    an actual reading. Otherwise, if the API's daily new-follower counts
    (last 30 days only) cover the gap, the count is estimated as today's
    total minus the followers gained since — an upper bound, because the API
    reports gains but not unfollows. Anything older is None.
    """
    earliest_gain = min(daily_gains) if daily_gains else None
    series = []
    for w in windows:
        end = date.fromisoformat(w["end"])
        actual = None
        for snap_day, count in snapshots.items():
            delta = (date.fromisoformat(snap_day) - end).days
            if 0 <= delta <= tolerance_days:
                actual = count
                break
        if actual is not None:
            series.append({"end": w["end"], "followers": actual, "estimated": False})
        elif earliest_gain and w["end"] >= earliest_gain:
            gained_since = sum(v for d, v in daily_gains.items() if d > w["end"])
            series.append(
                {"end": w["end"], "followers": current - gained_since, "estimated": True}
            )
        else:
            series.append({"end": w["end"], "followers": None, "estimated": False})
    return series
