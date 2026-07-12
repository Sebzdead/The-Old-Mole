import pytest

from src import instagram


def test_fetch_media_paginates(monkeypatch):
    pages = [
        {
            "data": [{"id": "1", "like_count": 5}],
            "paging": {"next": "https://graph.facebook.com/next"},
        },
        {"data": [{"id": "2", "like_count": 7}]},
    ]
    calls = []

    def fake_get(url, params):
        calls.append(url)
        return pages.pop(0)

    monkeypatch.setattr(instagram, "_get", fake_get)
    media = instagram.fetch_media("178414", "tok")
    assert [m["id"] for m in media] == ["1", "2"]
    assert calls[1] == "https://graph.facebook.com/next"


def test_fetch_media_stops_on_empty_page_with_next(monkeypatch):
    pages = [
        {
            "data": [{"id": "1", "like_count": 5}],
            "paging": {"next": "https://graph.facebook.com/next"},
        },
        {"data": [], "paging": {"next": "https://graph.facebook.com/next2"}},
    ]
    calls = []

    def fake_get(url, params):
        calls.append(url)
        return pages.pop(0)

    monkeypatch.setattr(instagram, "_get", fake_get)
    media = instagram.fetch_media("178414", "tok")
    assert [m["id"] for m in media] == ["1"]
    assert len(calls) == 2


def test_fetch_media_comments_stops_on_empty_page_with_next(monkeypatch):
    pages = [
        {
            "data": [{"text": "hi", "like_count": 1}],
            "paging": {"next": "https://graph.facebook.com/next"},
        },
        {"data": [], "paging": {"next": "https://graph.facebook.com/next2"}},
    ]
    calls = []

    def fake_get(url, params):
        calls.append(url)
        return pages.pop(0)

    monkeypatch.setattr(instagram, "_get", fake_get)
    comments = instagram.fetch_media_comments("m1", "tok")
    assert [c["text"] for c in comments] == ["hi"]
    assert len(calls) == 2


def test_fetch_media_insights_flattens_values(monkeypatch):
    def fake_get(url, params):
        return {
            "data": [
                {"name": "reach", "values": [{"value": 1500}]},
                {"name": "saved", "values": [{"value": 12}]},
            ]
        }

    monkeypatch.setattr(instagram, "_get", fake_get)
    out = instagram.fetch_media_insights("m1", "tok", "FEED")
    assert out == {"reach": 1500, "saved": 12}


def test_fetch_media_insights_tolerates_errors(monkeypatch):
    def fake_get(url, params):
        raise RuntimeError("unsupported metric")

    monkeypatch.setattr(instagram, "_get", fake_get)
    assert instagram.fetch_media_insights("m1", "tok", "REELS") == {}


def test_fetch_media_insights_tolerates_non_runtime_errors(monkeypatch):
    def fake_get(url, params):
        raise ValueError("not json")

    monkeypatch.setattr(instagram, "_get", fake_get)
    assert instagram.fetch_media_insights("m1", "tok", "FEED") == {}


def test_fetch_media_comments_tolerates_non_runtime_errors(monkeypatch):
    def fake_get(url, params):
        raise ValueError("not json")

    monkeypatch.setattr(instagram, "_get", fake_get)
    assert instagram.fetch_media_comments("m1", "tok") == []


def test_compute_movers_requires_baseline_and_thresholds():
    snapshot = {
        "media": {
            "old_hot": {"engagement": 100, "delta": 10},
            "old_cold": {"engagement": 100, "delta": 10},
            "old_flat": {"engagement": 100, "delta": 40},
        }
    }
    media = [
        {"id": "old_hot", "like_count": 140, "comments_count": 10, "permalink": "p1"},
        {"id": "old_cold", "like_count": 105, "comments_count": 5, "permalink": "p2"},
        {"id": "old_flat", "like_count": 150, "comments_count": 0, "permalink": "p3"},
        {"id": "brand_new", "like_count": 999, "comments_count": 0, "permalink": "p4"},
        {"id": "recent1", "like_count": 500, "comments_count": 0, "permalink": "p5"},
    ]
    movers = instagram.compute_movers(media, snapshot, recent_ids={"recent1"})
    ids = [m["media_id"] for m in movers]
    # old_hot: delta 50 >= 20 and >= 2x prev delta 10 -> mover
    # old_cold: delta 10 < 20 -> no. old_flat: delta 50 < 2x40 -> no.
    # brand_new: no baseline -> no. recent1: excluded.
    assert ids == ["old_hot"]
    assert movers[0]["delta_engagement"] == 50


def test_build_snapshot_records_engagement_and_delta():
    old = {"media": {"a": {"engagement": 10, "delta": 0}}}
    media = [
        {"id": "a", "like_count": 25, "comments_count": 5},
        {"id": "b", "like_count": 7, "comments_count": 0},
    ]
    snap = instagram.build_snapshot(media, old, "2026-07-11")
    assert snap["snapshot_date"] == "2026-07-11"
    assert snap["media"]["a"] == {"engagement": 30, "delta": 20}
    assert snap["media"]["b"] == {"engagement": 7, "delta": 0}


def test_snapshot_roundtrip(tmp_path):
    path = str(tmp_path / "snap.json")
    assert instagram.load_snapshot(path) == {"media": {}}
    instagram.save_snapshot(path, {"snapshot_date": "d", "media": {"x": {}}})
    assert instagram.load_snapshot(path)["media"] == {"x": {}}


def test_save_snapshot_accepts_bare_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    instagram.save_snapshot("snap.json", {"snapshot_date": "d", "media": {}})
    assert instagram.load_snapshot("snap.json") == {"snapshot_date": "d", "media": {}}
