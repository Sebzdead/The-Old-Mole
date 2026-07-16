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


def _bd_profile(username, ts):
    return {
        "username": username,
        "followers_count": 1000,
        "media_count": 50,
        "media": {
            "data": [
                {"id": "new", "timestamp": ts, "like_count": 10, "caption": "recent"},
                {
                    "id": "old",
                    "timestamp": "2020-01-01T00:00:00+0000",
                    "like_count": 99,
                    "caption": "ancient",
                },
            ]
        },
    }


def test_load_instagram_competitors_reads_key_and_defaults(tmp_path):
    p = tmp_path / "channels.yml"
    p.write_text("channels: []\ninstagram_competitors:\n  - novaramedia\n")
    assert collect.load_instagram_competitors(str(p)) == ["novaramedia"]
    p2 = tmp_path / "empty.yml"
    p2.write_text("channels: []\n")
    assert collect.load_instagram_competitors(str(p2)) == []


def test_collect_instagram_competitors_writes_recent_posts(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setenv("IG_ACCESS_TOKEN", "tok")
    fresh = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%S+0000"
    )
    monkeypatch.setattr(
        collect.instagram,
        "fetch_business_discovery",
        lambda ig_id, tok, username, media_limit=25: _bd_profile(username, fresh),
    )
    collect.collect_instagram_competitors(str(tmp_path), "178", ["novaramedia"])
    import json

    payload = json.load(open(tmp_path / "instagram_competitors.json"))
    assert payload["profiles"][0]["username"] == "novaramedia"
    assert payload["profiles"][0]["followers_count"] == 1000
    ids = [p["id"] for p in payload["profiles"][0]["recent_posts"]]
    assert ids == ["new"]  # 2020 post filtered out
    assert payload["errors"] == {}


def test_collect_instagram_competitors_isolates_failures(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setenv("IG_ACCESS_TOKEN", "tok")
    fresh = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%S+0000"
    )

    def flaky(ig_id, tok, username, media_limit=25):
        if username == "broken":
            raise RuntimeError("no matching business profile")
        return _bd_profile(username, fresh)

    monkeypatch.setattr(collect.instagram, "fetch_business_discovery", flaky)
    collect.collect_instagram_competitors(str(tmp_path), "178", ["broken", "good"])
    import json

    payload = json.load(open(tmp_path / "instagram_competitors.json"))
    assert [p["username"] for p in payload["profiles"]] == ["good"]
    assert "broken" in payload["errors"]


def test_collect_instagram_competitors_raises_when_all_fail(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_ACCESS_TOKEN", "tok")

    def broken(ig_id, tok, username, media_limit=25):
        raise RuntimeError("boom")

    monkeypatch.setattr(collect.instagram, "fetch_business_discovery", broken)
    import pytest

    with pytest.raises(RuntimeError, match="all"):
        collect.collect_instagram_competitors(str(tmp_path), "178", ["a", "b"])


def test_collect_instagram_competitors_skips_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_ACCESS_TOKEN", "tok")
    collect.collect_instagram_competitors(str(tmp_path), "178", [])
    import os

    assert not os.path.exists(tmp_path / "instagram_competitors.json")
