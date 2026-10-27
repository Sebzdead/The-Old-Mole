from datetime import date

from src import history


def test_week_windows_are_consecutive_and_end_on_last_day():
    windows = history.week_windows(date(2026, 10, 24), weeks=3)
    assert windows == [
        {"start": "2026-10-04", "end": "2026-10-10"},
        {"start": "2026-10-11", "end": "2026-10-17"},
        {"start": "2026-10-18", "end": "2026-10-24"},
    ]


def test_bucket_daily_sums_into_windows():
    windows = history.week_windows(date(2026, 10, 14), weeks=2)
    rows = [
        {"day": "2026-09-30", "views": 5},  # before both windows
        {"day": "2026-10-02", "views": 10},
        {"day": "2026-10-08", "views": 20},
        {"day": "2026-10-14", "views": 30},
    ]
    weekly = history.bucket_daily(rows, windows, ["views"])
    assert [w["views"] for w in weekly] == [10, 50]


def test_subscriber_totals_back_calculate_from_latest():
    weekly = [
        {"subscribersGained": 10, "subscribersLost": 2},
        {"subscribersGained": 30, "subscribersLost": 5},
    ]
    assert history.subscriber_totals(weekly, 1000) == [975, 1000]


def test_pct_change_handles_missing_baseline():
    assert history.pct_change(150, 100) == 50.0
    assert history.pct_change(150, 0) is None
    assert history.pct_change(None, 100) is None


def test_views_in_first_days_counts_from_publish_day():
    daily = {"2026-10-01": 100, "2026-10-02": 50, "2026-10-03": 25}
    assert history.views_in_first_days(daily, date(2026, 10, 1), 2) == 150


def test_compare_to_baseline_needs_enough_history():
    assert history.compare_to_baseline(200, [100, 50, 150]) == {
        "median": 100, "ratio": 2.0, "baseline_n": 3,
    }
    assert history.compare_to_baseline(200, [100, None])["ratio"] is None


def test_follower_series_prefers_snapshots_then_estimates():
    windows = history.week_windows(date(2026, 10, 24), weeks=3)
    snapshots = {"2026-10-26": 1000}
    gains = {"2026-10-12": 5, "2026-10-20": 10, "2026-10-25": 3}
    series = history.follower_series(windows, snapshots, 1000, gains)
    assert series[2] == {"end": "2026-10-24", "followers": 1000, "estimated": False}
    assert series[1] == {"end": "2026-10-17", "followers": 987, "estimated": True}
    # 2026-10-10 is before the earliest daily gain, so there is no estimate.
    assert series[0]["followers"] is None


def test_followers_roundtrip(tmp_path):
    path = tmp_path / "state" / "followers.json"
    history.save_followers(str(path), {"2026-10-26": 2, "2026-10-19": 1})
    assert history.load_followers(str(path)) == {"2026-10-19": 1, "2026-10-26": 2}
