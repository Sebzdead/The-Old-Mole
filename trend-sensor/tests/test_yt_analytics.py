import pytest

from src import yt_analytics


class _FakeRequest:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeReports:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeRequest(self._responses.pop(0))


class FakeAnalyticsClient:
    def __init__(self, responses):
        self._reports = _FakeReports(responses)

    def reports(self):
        return self._reports


def test_get_analytics_client_requires_env(monkeypatch):
    for var in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="YT_CLIENT_ID"):
        yt_analytics.get_analytics_client()


def test_channel_week_metrics_zips_headers_and_row():
    client = FakeAnalyticsClient([
        {
            "columnHeaders": [{"name": "views"}, {"name": "likes"}],
            "rows": [[1200, 80]],
        }
    ])
    out = yt_analytics.channel_week_metrics(client, "2026-07-03", "2026-07-09")
    assert out == {"views": 1200, "likes": 80}


def test_video_week_metrics_keyed_by_video_id():
    client = FakeAnalyticsClient([
        {
            "columnHeaders": [{"name": "video"}, {"name": "views"}, {"name": "likes"}],
            "rows": [["abc", 500, 40], ["def", 100, 5]],
        }
    ])
    out = yt_analytics.video_week_metrics(
        client, ["abc", "def"], "2026-07-03", "2026-07-09"
    )
    assert out["abc"] == {"views": 500, "likes": 40}
    assert out["def"]["views"] == 100


def test_back_catalog_movers_excludes_recent_and_applies_thresholds():
    this_week = {"rows": [["old1", 900], ["new1", 800], ["old2", 150], ["old3", 400]]}
    prev_week = {"rows": [["old1", 100], ["old3", 350]]}
    client = FakeAnalyticsClient([this_week, prev_week])
    movers = yt_analytics.back_catalog_movers(
        client,
        recent_video_ids={"new1"},
        this_start="2026-07-03",
        this_end="2026-07-09",
        prev_start="2026-06-26",
        prev_end="2026-07-02",
    )
    ids = [m["video_id"] for m in movers]
    assert ids == ["old1"]  # new1 excluded; old2 under min views; old3 under 2x ratio
    assert movers[0]["views_prev_week"] == 100
