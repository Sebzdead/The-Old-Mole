import pytest

from src import fetcher


def test_get_youtube_client_raises_without_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY"):
        fetcher.get_youtube_client()


def test_video_type_detects_shorts_and_live():
    assert fetcher.video_type({"contentDetails": {"duration": "PT45S"}}) == "short"
    assert fetcher.video_type({"contentDetails": {"duration": "PT2M59S"}}) == "short"
    assert fetcher.video_type({"contentDetails": {"duration": "PT1H2M"}}) == "video"
    assert fetcher.video_type(
        {"contentDetails": {"duration": "PT1H"}, "liveStreamingDetails": {}}
    ) == "video"
    assert fetcher.video_type(
        {"contentDetails": {"duration": "PT1H"}, "liveStreamingDetails": {"actualStartTime": "x"}}
    ) == "live"
