from datetime import date

import collect


def test_reporting_windows_account_for_analytics_lag():
    win = collect.reporting_windows(date(2026, 7, 13))  # a Monday
    assert win["this_start"] == "2026-07-05"
    assert win["this_end"] == "2026-07-11"
    assert win["prev_start"] == "2026-06-28"
    assert win["prev_end"] == "2026-07-04"


def test_run_source_records_success_and_failure():
    statuses = {}
    ok = collect.run_source(statuses, "good", lambda: 42)
    bad = collect.run_source(statuses, "bad", lambda: 1 / 0)
    assert ok == 42
    assert bad is None
    assert statuses["good"] == {"ok": True, "error": None}
    assert statuses["bad"]["ok"] is False
    assert "division" in statuses["bad"]["error"]
