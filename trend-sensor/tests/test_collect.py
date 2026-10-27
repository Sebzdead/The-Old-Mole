from datetime import date, timedelta

import collect


def test_reporting_windows_account_for_analytics_lag():
    win = collect.reporting_windows(date(2026, 7, 13))  # a Monday
    assert win["this_start"] == "2026-07-05"
    assert win["this_end"] == "2026-07-11"
    assert win["prev_start"] == "2026-06-28"
    assert win["prev_end"] == "2026-07-04"


def test_reporting_windows_anchor_to_real_data_availability():
    # Lag is 3 days, not the assumed 2: the window must shift back a day
    # rather than reaching past the last day with data.
    win = collect.reporting_windows(date(2026, 8, 24), anchor_end="2026-08-21")
    assert win["this_start"] == "2026-08-15"
    assert win["this_end"] == "2026-08-21"
    assert win["prev_start"] == "2026-08-08"
    assert win["prev_end"] == "2026-08-14"


def test_reporting_windows_are_always_equal_length():
    for anchor in (None, "2026-08-21", "2026-08-19"):
        win = collect.reporting_windows(date(2026, 8, 24), anchor_end=anchor)
        this_len = date.fromisoformat(win["this_end"]) - date.fromisoformat(
            win["this_start"]
        )
        prev_len = date.fromisoformat(win["prev_end"]) - date.fromisoformat(
            win["prev_start"]
        )
        assert this_len == prev_len == timedelta(days=6)
        # windows must abut, never overlap
        assert date.fromisoformat(win["prev_end"]) + timedelta(days=1) == (
            date.fromisoformat(win["this_start"])
        )


def test_run_source_records_success_and_failure():
    statuses = {}
    ok = collect.run_source(statuses, "good", lambda: 42)
    bad = collect.run_source(statuses, "bad", lambda: 1 / 0)
    assert ok == 42
    assert bad is None
    assert statuses["good"] == {"ok": True, "error": None}
    assert statuses["bad"]["ok"] is False
    assert "division" in statuses["bad"]["error"]


def test_run_source_redacts_credentials_in_errors():
    statuses = {}

    def boom():
        raise RuntimeError(
            "HttpError 403 https://x.com/v3?key=SECRETKEY&access_token=SECRETTOK&a=1"
        )

    collect.run_source(statuses, "s", boom)
    err = statuses["s"]["error"]
    assert "SECRETKEY" not in err
    assert "SECRETTOK" not in err
    assert "REDACTED" in err
